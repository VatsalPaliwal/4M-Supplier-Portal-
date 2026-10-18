// Show/hide the per-row file upload input based on the Yes/No selection.
document.querySelectorAll('.fourm-select').forEach(function (select) {
  select.addEventListener('change', function () {
    var target = this.getAttribute('data-target');
    var fileInput = document.getElementById(target + '-file');
    if (!fileInput) return;

    if (this.value === 'Yes') {
      fileInput.classList.remove('d-none');
    } else {
      fileInput.classList.add('d-none');
      fileInput.value = '';
    }
  });
});

// Reflect the selected month in the declaration sentence.
var monthSelect = document.getElementById('reportMonth');
var declarationMonth = document.getElementById('declarationMonth');
if (monthSelect && declarationMonth) {
  monthSelect.addEventListener('change', function () {
    var selectedOption = this.options[this.selectedIndex];
    declarationMonth.textContent = this.value === '' ? '___' : selectedOption.text;
  });
}

// Two-step submission safety: Reveal Preview & Upload after clicking Save as Draft
var saveDraftBtn = document.getElementById('saveDraftBtn');
var finalActionButtons = document.getElementById('finalActionButtons');

if (saveDraftBtn && finalActionButtons) {
  saveDraftBtn.addEventListener('click', function (e) {
    // Prevent the form from submitting instantly on the first click
    e.preventDefault();
    
    // Hide 'Save as Draft' and reveal Preview/Upload options properly using d-flex
    this.classList.add('d-none');
    finalActionButtons.classList.remove('d-none');
    finalActionButtons.classList.add('d-flex');
  });
}