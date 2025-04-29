(function($) {
    $ = $ || django.jQuery;
    console.log("================================================================")
    $(document).ready(function() {
        if ($('body').hasClass('change-form')) {
            var submitRow = $('.submit-row');
            
            if (submitRow.length) {
                var runButton = $('<input type="submit" value="Run Embedding Job" name="_run_now" class="default" style="background-color: #5cb85c; margin-right: 5px;">');
                
                runButton.click(function() {
                    return confirm('Are you sure you want to run this embedding job?\n\nThis will start the embedding generation process for the selected node labels.');
                });
                
                submitRow.prepend(runButton);
            }
        }
        
        $('<style>')
            .prop('type', 'text/css')
            .html(`
                /* Progress bar styling */
                .progress {
                    height: 20px;
                    margin-bottom: 20px;
                    overflow: hidden;
                    background-color: #f5f5f5;
                    border-radius: 4px;
                    box-shadow: inset 0 1px 2px rgba(0,0,0,.1);
                }
                .progress-bar {
                    float: left;
                    width: 0;
                    height: 100%;
                    font-size: 12px;
                    line-height: 20px;
                    color: #fff;
                    text-align: center;
                    background-color: #337ab7;
                    box-shadow: inset 0 -1px 0 rgba(0,0,0,.15);
                    transition: width .6s ease;
                }
                .progress-bar-success {
                    background-color: #5cb85c;
                }
                .progress-bar-warning {
                    background-color: #f0ad4e;
                }
                .progress-bar-danger {
                    background-color: #d9534f;
                }
            `)
            .appendTo('head');
        
        if ($('body').hasClass('change-form') && $('#id_status').length) {
            var statusField = $('#id_status');
            var completionField = $('#id_completion_percentage');
            
            if (statusField.val() === 'processing' && completionField.length) {
                var completionValue = parseInt(completionField.val() || '0');
                
                var progressBar = $(`
                    <div class="progress">
                        <div class="progress-bar progress-bar-striped active" role="progressbar" 
                             aria-valuenow="${completionValue}" aria-valuemin="0" aria-valuemax="100" 
                             style="width: ${completionValue}%;">
                            ${completionValue}% Complete
                        </div>
                    </div>
                `);
                
                completionField.after(progressBar);
                
                setTimeout(function() {
                    location.reload();
                }, 10000); 
            }
        }
    });
})(window.jQuery || django.jQuery);