frappe.require([
    '/assets/csf_tz/js/csfUtlis.js',
    '/assets/csf_tz/js/shortcuts.js'
]);

frappe.ui.form.on("Purchase Order", {
    refresh: (frm) => {
        const limit_uom_as_item_uom = getValue("CSF TZ Settings", "CSF TZ Settings", "limit_uom_as_item_uom");
        if (limit_uom_as_item_uom == 1) {
            frm.set_query("uom", "items", function (frm, cdt, cdn) {
                let row = locals[cdt][cdn];
                return {
                    query:
                        "erpnext.accounts.doctype.pricing_rule.pricing_rule.get_item_uoms",
                    filters: {
                        value: row.item_code,
                        apply_on: "Item Code",
                    },
                };
            });
        }
    },
    supplier: function (frm) {
        setTimeout(function () {
            if (!frm.doc.tax_category) {
                frappe.call({
                    method: "csf_tz.custom_api.get_tax_category",
                    args: {
                        doc_type: frm.doc.doctype,
                        company: frm.doc.company,
                    },
                    callback: function (r) {
                        if (!r.exc) {
                            frm.set_value("tax_category", r.message);
                            frm.trigger("tax_category");
                        }
                    }
                });
            }
        }, 1000);
    },
    setup: function (frm) {
        frm.set_query("taxes_and_charges", function () {
            return {
                "filters": {
                    "company": frm.doc.company,
                }
            };
        });
    },
});

frappe.ui.form.on("Purchase Order Item", {
    item_code: async function (frm, cdt, cdn) {
        var item = locals[cdt][cdn];
        var price_list = await get_price_list(item.item_code, item.warehouse);
        frappe.model.set_value(cdt, cdn, "price_list_rate", price_list);
        frappe.model.set_value(cdt, cdn, "rate", price_list);
        frappe.model.set_value(cdt, cdn, "amount", price_list * item.qty);
    },
    warehouse: async function (frm, cdt, cdn) {
        var item = locals[cdt][cdn];
        var price_list = await get_price_list(item.item_code, item.warehouse);
        frappe.model.set_value(cdt, cdn, "price_list_rate", price_list);
        frappe.model.set_value(cdt, cdn, "rate", price_list);
        frappe.model.set_value(cdt, cdn, "amount", price_list * item.qty);
    },
})

async function get_price_list(item_code, warehouse) {
    var check = await frappe.db.get_single_value("CSF TZ Settings", "target_warehouse_based_price_list");
    if (check == 0) {
        return null;
    }
    if (!item_code || !warehouse) {
        frappe.throw("Both Item Code and Warehouse are required");
    }

    var price_list = await frappe.db.get_value("Warehouse", warehouse, "price_list");
    if (price_list.message.price_list) {
        var price_list_rate = await frappe.db.get_value("Item Price", { item_code: item_code, price_list: price_list.message.price_list }, "price_list_rate");
        return price_list_rate.message.price_list_rate;
    } else {
        frappe.throw("Price List not found. Please set one in Warehouse " + warehouse);
    }
}