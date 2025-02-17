django.jQuery(document).ready(function($) {
    var $typeSelect = $('#id_type');
    var $enterpriseFields = $('.enterprise-only');

    function toggleEnterpriseFields() {
        if ($typeSelect.val() === 'enterprise') {
            $enterpriseFields.show();
        } else {
            $enterpriseFields.hide();
        }
    }

    $typeSelect.on('change', toggleEnterpriseFields);
    toggleEnterpriseFields(); // Initial state
});