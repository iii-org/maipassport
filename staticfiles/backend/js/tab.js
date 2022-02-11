    $(function() {
        $( "#tabs" ).tabs({
            create: function(event, ui) { window.location.hash = ui.panel.attr('id');},
            activate: function(event, ui) { window.location.hash = ui.newPanel.attr('id');}
        });
    });