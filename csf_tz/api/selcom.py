from selcom_apigw_client import apigwClient
import json
import frappe
from frappe import _
import base64
import re

# Initialize API client
selcom_settings = frappe.get_doc("Selcom Settings")
apiKey = selcom_settings.get_password("api_key")
apiSecret = selcom_settings.get_password("api_secret")
baseUrl = selcom_settings.get_password("base_url")


def create_order_log(
    method, status, request_json, response, reference, order_id, docname=None
):
    doc = frappe.new_doc("Selcom Order Log")
    doc.date = frappe.utils.today()
    doc.time = frappe.utils.nowtime()
    doc.method = method
    if docname:
        doc.registration_docname = docname
    doc.status = status
    doc.reference = reference
    doc.order_id = order_id
    doc.request_data = json.dumps(request_json, indent=4)
    doc.response_data = json.dumps(response, indent=4)
    doc.insert(ignore_permissions=True)
    frappe.db.commit()


@frappe.whitelist(allow_guest=True)
def create_order_minimal(order_data):
    order_data = json.loads(order_data)
    client = apigwClient.Client(baseUrl, apiKey, apiSecret)

    package_prices = {
        "Individual": {
            "Basic": {"USD": 1, "TZS": 210},
            "Standard": {"USD": 225, "TZS": 607500},
            "Premium": {"USD": 450, "TZS": 1215000},
        },
        "Corporate": {
            "Basic": {"USD": 2, "TZS": 220},
            "Standard": {"USD": 450, "TZS": 1215000},
            "Premium": {"USD": 1250, "TZS": 3375000},
            "VIP": {"USD": 2500, "TZS": 6750000},
        },
        "Sponsor": {
            "Bronze": {"USD": 3, "TZS": 230},
            "Silver": {"USD": 7000, "TZS": 18900000},
            "Gold": {"USD": 12000, "TZS": 32400000},
            "Platinum": {"USD": 25000, "TZS": 67500000},
        },
    }

    redirect_url = "https://tafina-rsvp.aakvaerp.com/thank-you-for-the-payment"
    call_back_url = "https://tafina-rsvp.aakvaerp.com/api/method/csf_tz.api.selcom.create_webhook_callback"
    # cancel_urls = {
    #     "Corporate": "https://tafina-rsvp.aakvaerp.com/corporate-eaif-2024/new",
    #     "Sponsor": "https://tafina-rsvp.aakvaerp.com/sponsor-eaif-2024/new",
    #     "Individual": "https://tafina-rsvp.aakvaerp.com/eaif-2024/new",
    # }
    # cancel_url = cancel_urls.get(form_type, "")
    # cancel_encoded_url = base64.b64encode(cancel_url.encode()).decode()

    # # Encode the URL
    redirect_encoded_url = base64.b64encode(redirect_url.encode()).decode()
    callback_encoded_url = base64.b64encode(call_back_url.encode()).decode()

    form_type = order_data.get("form_type")
    if form_type not in package_prices:
        frappe.throw("Unknown form type")

    package_type = order_data.get("package")
    currency = order_data.get("package_currency")
    try:
        amount = package_prices[form_type][package_type][currency]
    except KeyError:
        frappe.throw("Package type or currency is not defined correctly.")

    # Define the regex pattern to check if the phone number starts with '255' and followed by 9 more digits
    pattern = r"^255\d{9}$"

    # Check if the phone number matches the pattern
    if re.match(pattern, order_data.get("mobile")):
        phone_number = order_data.get("mobile")
    else:
        frappe.throw(
            "Invalid phone number. It should start with '255' and followed by 9 digits."
        )

    country = frappe.get_doc("Country", order_data.get("country"))
    order_id = frappe.generate_hash(length=10)

    orderDict = {
        "vendor": selcom_settings.get_password("vendor"),
        "order_id": order_id,
        "buyer_email": order_data.get("email"),
        "buyer_name": f"{order_data.get('first_name')} {order_data.get('last_name')}",
        "buyer_userid": "",
        "buyer_phone": phone_number,
        "gateway_buyer_uuid": "",
        "amount": amount,
        "currency": currency,
        "payment_methods": "ALL",
        "redirect_url": redirect_encoded_url,
        "cancel_url": "",
        "webhook": callback_encoded_url,
        "billing.firstname": order_data.get("first_name"),
        "billing.lastname": order_data.get("last_name"),
        "billing.address_1": order_data.get("address_1"),
        "billing.address_2": "",
        "billing.city": order_data.get("city"),
        "billing.state_or_region": order_data.get("state_or_region"),
        "billing.postcode_or_pobox": order_data.get("postcode_or_pobox"),
        "billing.country": country.code.upper(),
        "billing.phone": phone_number,
        "buyer_remarks": "Payment",
        "merchant_remarks": "Payment",
        "no_of_items": 1,
    }

    # API endpoint
    orderPath = "/checkout/create-order"

    # Send order request
    try:
        response = client.postFunc(orderPath, orderDict)
        if response.get("resultcode") != "000":
            frappe.log_error(
                f"Error on Create Order {response.get('reference')} to Payment Gateway",
                response,
            )
            create_order_log(
                "Create Order",
                "Failed",
                orderDict,
                response,
                reference=response.get("reference"),
                order_id=order_id,
            )
            return response

        else:

            # Decode the Base64 URL from the payment_gateway_url
            encoded_url = response["data"][0]["payment_gateway_url"]
            decoded_url = base64.b64decode(encoded_url).decode("utf-8")
            # Insert data in docype
            docname = insert_based_on_form_type(order_data, order_id, decoded_url)
            frappe.msgprint(_("Order created successfully"), alert=True)
            create_order_log(
                "Create Order",
                "Success",
                orderDict,
                response,
                reference=response.get("reference"),
                order_id=order_id,
                docname=docname,
            )
            return {
                "success": True,
                "message": "Payment notification logged successfully.",
                "payment_gateway_url": decoded_url,
            }

    except Exception as e:
        frappe.log_error(
            f"Error on Create Order {response.get('reference')} to Payment Gateway",
            str(e),
        )
        create_order_log(
            "Create Order",
            "Failed",
            orderDict,
            str(e),
            reference=response.get("reference"),
            order_id=order_id,
        )
        frappe.throw(
            _("Failed to create order, please try again, or contact the administrator")
        )


@frappe.whitelist(allow_guest=True)
def create_webhook_callback(*args, **kwargs):
    doc = frappe.new_doc("Selcom Webhook Callback")
    doc.data = frappe.as_json(kwargs)
    doc.insert(ignore_permissions=True)
    frappe.db.commit()


@frappe.whitelist(allow_guest=True)
def get_order_id_status(order_log, order_id):
    client = apigwClient.Client(baseUrl, apiKey, apiSecret)
    orderStatusDict = {"order_id": order_id}
    orderStatusPath = "/checkout/order-status"
    response = client.getFunc(orderStatusPath, orderStatusDict)

    doc = frappe.get_doc("Selcom Order Log", order_log)
    doc.order_id_status_data = json.dumps(response, indent=4)
    doc.save(ignore_permissions=True)
    frappe.db.commit()


@frappe.whitelist(allow_guest=True)
def insert_based_on_form_type(order_data, order_id, payment_url=None):

    form_docs = {
        "Individual": "Registration",
        "Corporate": "Corporate Registration",
        "Sponsor": "Sponsor Registration",
    }
    form_type = order_data.get("form_type")
    target_doctype = form_docs.get(form_type)

    if not target_doctype:
        frappe.throw("Invalid form type provided.")

    try:
        if isinstance(order_data, str):
            order_data = json.loads(order_data)

        doc = frappe.new_doc(target_doctype)

        for field, value in order_data.items():
            if hasattr(doc, field):
                setattr(doc, field, value)

        doc.full_name = f"{order_data.get('first_name')} {order_data.get('last_name')}"
        doc.order_id = order_id
        doc.payment_url = payment_url
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return doc.name

    except Exception as e:
        frappe.log_error(f"Error in insert_based_on_form_type: {str(e)}")
        frappe.throw(f"An error occurred: {str(e)}")
