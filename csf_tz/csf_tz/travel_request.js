frappe.ui.form.on('Travel Request', {
    refresh: function (frm) {
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button('Create Employee Advance', function () {
                checkSettingsAndCreateEA(frm);
            });
        }
    }
});

function makeFrappeCall(method, args, callback) {
    frappe.call({
        method: method,
        args: args,
        callback: callback
    });
}

function checkSettingsAndCreateEA(frm) {
    makeFrappeCall(
        'frappe.client.get_value',
        {
            doctype: 'CSF TZ Settings',
            fieldname: ['track_unclaimed_employee_advances']
        },
        function (settings_response) {
            if (settings_response && settings_response.message) {
                const trackUnclaimed = settings_response.message.track_unclaimed_employee_advances;
                if (trackUnclaimed != 0) {
                    checkUnclaimedCountAndCreateEA(frm);
                } else {
                    frappe.msgprint(__('Please enable <b>Track Unclaimed Employee Advances</b> in the CSF TZ Settings.'));
                }
            }
        }
    );
}

function checkUnclaimedCountAndCreateEA(frm) {
    makeFrappeCall(
        'frappe.client.get_list',
        {
            doctype: 'Employee Advance',
            filters: {
                status: 'Draft'
            },
            fields: ['name']
        },
        function (ea_response) {
            if (ea_response && ea_response.message) {
                let unclaimed_count = ea_response.message.length;
                checkMaxUnclaimedAndCreateEA(frm, unclaimed_count);
            }
        }
    );
}

function checkMaxUnclaimedAndCreateEA(frm, unclaimed_count) {
    makeFrappeCall(
        'frappe.client.get_value',
        {
            doctype: 'Company',
            fieldname: ['max_unclaimed_ea', 'abbr']
        },
        function (company_response) {
            if (company_response && company_response.message) {
                let max_unclaimed_ea = company_response.message.max_unclaimed_ea;
                let company_abbr = company_response.message.abbr;

                if (unclaimed_count < max_unclaimed_ea) {
                    createEmployeeAdvance(frm, company_abbr);
                } else {
                    frappe.msgprint(__('The maximum number of unclaimed Employee Advances has been reached. Cannot create a new Employee Advance.'));
                }
            }
        }
    );
}

function createEmployeeAdvance(frm, company_abbr) {
    let advance_account = "Employee Advances - " + company_abbr;

    makeFrappeCall(
        'frappe.client.insert',
        {
            doc: {
                doctype: 'Employee Advance',
                employee: frm.doc.employee,
                employee_name: frm.doc.employee_name,
                posting_date: frappe.datetime.nowdate(),
                purpose: frm.doc.purpose_of_travel,
                advance_amount: frm.doc.costings.reduce((total, costing) => total + costing.total_amount, 0),
                company: frm.doc.company,
                advance_account: advance_account,
                exchange_rate: 1,
                status: 'Draft'
            }
        },
        function (response) {
            if (response && response.message) {
                frappe.set_route('Form', 'Employee Advance', response.message.name);
            }
        }
    );
}
