"""
Contact Validator: Validates syntax, DNS MX records, domain associations,
and E.164 phone numbering plan compliance.
Never performs invasive SMTP mailbox probing or live call testing.
"""
import logging
from typing import Dict, Any, Optional
import dns.resolver
from email_validator import validate_email, EmailNotValidError
import phonenumbers
from app.utils.url_utils import extract_domain

logger = logging.getLogger(__name__)


class ContactValidator:
    @staticmethod
    def validate_email_channel(
        email: str,
        company_domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate email syntax, domain format, and DNS MX record.
        Checks company attribution (whether email domain matches company domain).
        """
        result = {
            "syntax_valid": False,
            "mx_record_found": False,
            "domain_valid": False,
            "company_attributed": False,
            "normalized_email": email.strip().lower(),
            "validation_error": None,
        }

        if not email or "@" not in email:
            result["validation_error"] = "Missing '@' in email address"
            return result

        # 1. Syntax check with email-validator
        try:
            valid_info = validate_email(email, check_deliverability=False)
            result["syntax_valid"] = True
            result["domain_valid"] = True
            result["normalized_email"] = valid_info.normalized
            email_domain = valid_info.domain.lower()
        except EmailNotValidError as e:
            result["validation_error"] = str(e)
            return result
        except Exception as e:
            result["validation_error"] = f"Syntax validation error: {e}"
            return result

        # 2. Company attribution
        if company_domain:
            clean_company_domain = company_domain.lower().replace("www.", "").strip()
            if email_domain == clean_company_domain or email_domain.endswith(f".{clean_company_domain}"):
                result["company_attributed"] = True

        # 3. DNS MX check (using dnspython with conservative timeout)
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = 2.0
            resolver.lifetime = 2.0
            answers = resolver.resolve(email_domain, "MX")
            if answers and len(answers) > 0:
                result["mx_record_found"] = True
        except Exception:
            # Fallback check for A record if no MX (some domains route mail via root A record)
            try:
                a_answers = resolver.resolve(email_domain, "A")
                if a_answers and len(a_answers) > 0:
                    result["mx_record_found"] = False
                    result["domain_valid"] = True
            except Exception:
                result["mx_record_found"] = False

        return result

    @staticmethod
    def validate_phone_channel(
        phone_raw: str,
        default_region: str = "IN"
    ) -> Dict[str, Any]:
        """
        Validate phone numbering plan validity, possibility, and country format.
        """
        result = {
            "syntax_valid": False,
            "is_possible": False,
            "is_valid": False,
            "e164": None,
            "country_code": None,
            "national_format": None,
            "validation_error": None,
        }

        if not phone_raw:
            result["validation_error"] = "Empty phone number"
            return result

        try:
            parsed = phonenumbers.parse(phone_raw, default_region)
            is_possible = phonenumbers.is_possible_number(parsed)
            is_valid = phonenumbers.is_valid_number(parsed)

            result["syntax_valid"] = True
            result["is_possible"] = is_possible
            result["is_valid"] = is_valid
            result["country_code"] = parsed.country_code

            if is_valid or is_possible:
                result["e164"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                result["national_format"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        except Exception as e:
            result["validation_error"] = str(e)

        return result
