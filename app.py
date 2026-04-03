from flask import Flask, render_template, request
import phonenumbers
from phonenumbers import geocoder, carrier, timezone
from phonenumbers.phonenumberutil import number_type, PhoneNumberType

app = Flask(__name__)

def get_number_type(num_type):
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

@app.route("/", methods=["GET", "POST"])
def index():
    result = None

    if request.method == "POST":
        number = request.form.get("phone")

        try:
            parsed_number = phonenumbers.parse(number)

            if phonenumbers.is_valid_number(parsed_number):
                # Location
                location = geocoder.description_for_number(parsed_number, "en")

                # Carrier
                sim_carrier = carrier.name_for_number(parsed_number, "en")

                # Timezone
                time_zones = timezone.time_zones_for_number(parsed_number)

                # Number Type
                num_type = number_type(parsed_number)
                num_type_str = get_number_type(num_type)

                # Country Code & National Number
                country_code = parsed_number.country_code
                national_number = parsed_number.national_number

                # Formatted Numbers
                e164_format = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
                international_format = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                national_format = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.NATIONAL)

                # Possible Number Check
                is_possible = phonenumbers.is_possible_number(parsed_number)

                # Region Code
                region_code = phonenumbers.region_code_for_number(parsed_number)

                result = {
                    "valid": True,
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
                    "region_code": region_code,
                }
            else:
                result = {"valid": False}

        except Exception as e:
            result = {"error": str(e)}

    return render_template("index.html", result=result)

if __name__ == "__main__":
    app.run(debug=True)