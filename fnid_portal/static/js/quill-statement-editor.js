(function () {
  var editorEl = document.getElementById('statement-editor');
  var hiddenInput = document.getElementById('statement_text_field');
  if (!editorEl || !hiddenInput || typeof Quill === 'undefined') return;

  var initialHtml = hiddenInput.value || '';
  var placeholder = editorEl.dataset.placeholder ||
    'Compose here. Use the toolbar for emphasis, lists, and quotations.';

  var quill = new Quill('#statement-editor', {
    theme: 'snow',
    placeholder: placeholder,
    modules: {
      toolbar: [
        [{ header: [false, 2, 3] }],
        ['bold', 'italic', 'underline'],
        [{ list: 'ordered' }, { list: 'bullet' }],
        ['blockquote'],
        ['clean'],
      ],
    },
  });

  if (initialHtml) {
    var delta = quill.clipboard.convert({ html: initialHtml });
    quill.setContents(delta, 'silent');
  }

  var form = editorEl.closest('form');
  if (form) {
    form.addEventListener('submit', function () {
      hiddenInput.value = quill.root.innerHTML;
    });
  }
})();
