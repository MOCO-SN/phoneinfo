import os
import re
from typing import Optional, Dict, Any

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import phonenumbers
from phonenumbers import geocoder, carrier, timezone
from phonenumbers.phonenumberutil import number_type, PhoneNumberType, NumberParseException

from leakosint_service import (
    LeakOSINTClient,
    calculate_query_complexity,
    calculate_estimated_price,
    DEFAULT_API_URL
)

# Load environment variables (.env file)
load_dotenv()

app = Flask(__name__)

# Initialize LeakOSINT Client with environment token if available
leakosint_client = LeakOSINTClient()


def get_number_type(num_type: int) -> str:
    types = {
        PhoneNumberType.MOBILE: "Mobile",
        PhoneNumberType.FIXED_LINE: "Fixed Line",
        PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed Line or Mobile",
        PhoneNumberType.TOLL_FREE: "Toll Free",
        PhoneNumberType.PREMIUM_RATE: "Premium Rate",
        PhoneNumberType.SHARED_COST: "Shared Cost",
        PhoneNumberType.VOIP: "VoIP",
        PhoneNumberType.PERSONAL_NUMBER: "Personal Number",
        PhoneNumberType.PAGER: "Pager",
        PhoneNumberType.UAN: "UAN",
        PhoneNumberType.VOICEMAIL: "Voicemail",
        PhoneNumberType.UNKNOWN: "Unknown",
    }
    return types.get(num_type, "Unknown")


def parse_phone_info(phone_str: str) -> Dict[str, Any]:
    """
    Parses and extracts metadata from a phone number string.
    Tries parsing with leading '+' if missing.
    """
    raw_clean = phone_str.strip()
    if not raw_clean:
        return {"valid": False, "is_phone": False, "error": "Empty phone number."}

    # If it contains letters (except 'x' or 'ext' for extensions) or '@', it's likely an email or name
    if "@" in raw_clean or re.search(r"[a-wyzA-WYZ]", raw_clean):
        return {"valid": False, "is_phone": False, "error": "Input appears to be an email or text query, not a phone number."}

    candidates = [raw_clean]
    if not raw_clean.startswith("+"):
        candidates.append("+" + raw_clean)

    parsed_number = None
    last_error = None

    for candidate in candidates:
        try:
            parsed = phonenumbers.parse(candidate, None)
            if phonenumbers.is_possible_number(parsed):
                parsed_number = parsed
                break
            elif not parsed_number:
                parsed_number = parsed
        except NumberParseException as e:
            last_error = str(e)

    if not parsed_number:
        return {
            "valid": False,
            "is_phone": False,
            "error": last_error or "Invalid phone number pattern."
        }

    is_valid = phonenumbers.is_valid_number(parsed_number)
    is_possible = phonenumbers.is_possible_number(parsed_number)

    if not is_valid and not is_possible:
        return {
            "valid": False,
            "is_phone": True,
            "error": "The number format is invalid or incomplete."
        }

    # Extract phone intelligence
    location = geocoder.description_for_number(parsed_number, "en")
    sim_carrier = carrier.name_for_number(parsed_number, "en")
    time_zones = timezone.time_zones_for_number(parsed_number)
    num_type = number_type(parsed_number)
    num_type_str = get_number_type(num_type)
    country_code = parsed_number.country_code
    national_number = parsed_number.national_number

    e164_format = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
    international_format = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    national_format = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.NATIONAL)
    region_code = phonenumbers.region_code_for_number(parsed_number)

    return {
        "valid": is_valid,
        "is_phone": True,
        "location": location or "Unknown",
        "carrier": sim_carrier or "Unknown",
        "timezones": list(time_zones),
        "number_type": num_type_str,
        "country_code": f"+{country_code}",
        "national_number": national_number,
        "e164": e164_format,
        "international": international_format,
        "national": national_format,
        "is_possible": is_possible,
        "region_code": region_code or "Unknown",
    }


@app.route("/", methods=["GET", "POST"])
def index():
    phone_result = None
    leak_result = None
    pricing_info = None

    query_value = ""
    mode = "smart"  # 'smart', 'phone', or 'leak'
    limit = 100
    lang = "en"
    token = ""

    server_has_token = bool(os.environ.get("LEAKOSINT_API_TOKEN", "").strip())

    if request.method == "POST":
        query_value = request.form.get("query") or request.form.get("phone", "")
        mode = request.form.get("mode", "smart").lower()
        token = request.form.get("token", "").strip()
        
        try:
            limit = int(request.form.get("limit", 100))
        except (ValueError, TypeError):
            limit = 100
        
        lang = request.form.get("lang", "en").strip()

        # Check if user requested JSON response via accept header or query param
        wants_json = (
            request.args.get("format") == "json" or
            request.headers.get("Accept") == "application/json"
        )
    elif request.method == "GET" and request.args.get("query"):
        query_value = request.args.get("query", "")
        mode = request.args.get("mode", "smart").lower()
        token = request.args.get("token", "").strip()
        try:
            limit = int(request.args.get("limit", 100))
        except (ValueError, TypeError):
            limit = 100
        lang = request.args.get("lang", "en").strip()
        wants_json = request.args.get("format") == "json"
    else:
        wants_json = False

    query_value = query_value.strip()

    if query_value:
        # Calculate pricing information based on formula from documentation
        complexity, word_count, words = calculate_query_complexity(query_value)
        price_val = calculate_estimated_price(limit, complexity)
        pricing_info = {
            "complexity": complexity,
            "word_count": word_count,
            "words": words,
            "limit": limit,
            "price_usd": f"${price_val:.5f}",
        }

        # 1. Process Phone Intelligence if mode is 'smart' or 'phone'
        if mode in ("smart", "phone"):
            p_res = parse_phone_info(query_value)
            if mode == "phone" or p_res.get("is_phone"):
                phone_result = p_res

        # 2. Process LeakOSINT Breach Intelligence if mode is 'smart' or 'leak'
        if mode in ("smart", "leak"):
            active_token = token or os.environ.get("LEAKOSINT_API_TOKEN", "").strip()
            
            # If search is for a phone, we can query the E.164 formatted number or original query
            search_query = query_value
            if phone_result and phone_result.get("valid") and phone_result.get("e164"):
                search_query = phone_result["e164"]

            leak_result = leakosint_client.search(
                query=search_query,
                token=active_token,
                limit=limit,
                lang=lang,
                report_type="json",
            )

        if wants_json:
            return jsonify({
                "query": query_value,
                "mode": mode,
                "pricing": pricing_info,
                "phone_intelligence": phone_result,
                "leak_intelligence": leak_result,
            })

    # Backward compatibility with legacy template result structure
    legacy_result = phone_result if (phone_result and mode == "phone") else None

    return render_template(
        "index.html",
        query_value=query_value,
        phone_value=query_value,
        phone_result=phone_result,
        leak_result=leak_result,
        pricing_info=pricing_info,
        mode=mode,
        limit=limit,
        lang=lang,
        user_token=token,
        server_has_token=server_has_token,
        result=legacy_result
    )


@app.route("/api/lookup", methods=["GET", "POST"])
def api_lookup():
    """
    REST API endpoint for programmatic queries.
    Accepts JSON body or query parameters.
    """
    if request.is_json:
        data = request.get_json() or {}
        query = data.get("query") or data.get("phone", "")
        mode = data.get("mode", "smart")
        token = data.get("token", "")
        limit = data.get("limit", 100)
        lang = data.get("lang", "en")
    else:
        query = request.values.get("query") or request.values.get("phone", "")
        mode = request.values.get("mode", "smart")
        token = request.values.get("token", "")
        limit = request.values.get("limit", 100)
        lang = request.values.get("lang", "en")

    query = str(query).strip()
    if not query:
        return jsonify({"error": "Missing 'query' parameter"}), 400

    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 100

    complexity, word_count, words = calculate_query_complexity(query)
    price_val = calculate_estimated_price(limit, complexity)
    pricing = {
        "complexity": complexity,
        "word_count": word_count,
        "words": words,
        "limit": limit,
        "estimated_price_usd": f"${price_val:.5f}",
    }

    phone_data = None
    if mode in ("smart", "phone"):
        p_res = parse_phone_info(query)
        if mode == "phone" or p_res.get("is_phone"):
            phone_data = p_res

    leak_data = None
    if mode in ("smart", "leak"):
        active_token = token or os.environ.get("LEAKOSINT_API_TOKEN", "").strip()
        search_query = query
        if phone_data and phone_data.get("valid") and phone_data.get("e164"):
            search_query = phone_data["e164"]

        leak_data = leakosint_client.search(
            query=search_query,
            token=active_token,
            limit=limit,
            lang=lang,
            report_type="json",
        )

    return jsonify({
        "query": query,
        "mode": mode,
        "pricing": pricing,
        "phone_intelligence": phone_data,
        "leak_intelligence": leak_data,
    })


@app.route("/api/estimate-cost", methods=["GET"])
def api_estimate_cost():
    """
    Real-time price & complexity estimator according to LeakOSINT documentation formula:
    Price = 0.0002 * (5 + sqrt(Limit * Complexity))
    """
    query = request.args.get("query", "")
    try:
        limit = int(request.args.get("limit", 100))
    except (ValueError, TypeError):
        limit = 100

    complexity, word_count, words = calculate_query_complexity(query)
    price_val = calculate_estimated_price(limit, complexity)

    return jsonify({
        "query": query,
        "limit": limit,
        "complexity": complexity,
        "word_count": word_count,
        "words": words,
        "estimated_price_usd": f"${price_val:.5f}",
        "formula": "0.0002 * (5 + sqrt(Limit * Complexity))",
    })


if __name__ == "__main__":
    app.run(debug=True)
