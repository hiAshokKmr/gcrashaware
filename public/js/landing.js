// Landing Page Script
document.addEventListener('DOMContentLoaded', () => {
  // Check URL parameters for dynamic corridor targeting from ad click
  const params = new URLSearchParams(window.location.search);
  const corridorParam = params.get('corridor') || params.get('utm_term');
  if (corridorParam) {
    const select = document.getElementById('incidentLocation');
    for (let i = 0; i < select.options.length; i++) {
      if (select.options[i].text.toLowerCase().includes(corridorParam.toLowerCase())) {
        select.selectedIndex = i;
        break;
      }
    }
    const ticker = document.getElementById('tickerLocation');
    if (ticker) {
      ticker.textContent = `Targeted Dispatch Active for ${corridorParam} Corridor`;
    }
  }
});

async function submitLeadForm(event) {
  event.preventDefault();
  const submitBtn = document.getElementById('submitFormBtn');
  const successBanner = document.getElementById('formSuccessBanner');
  const form = document.getElementById('leadIntakeForm');

  const formData = {
    name: document.getElementById('fullName').value.trim(),
    phone: document.getElementById('phone').value.trim(),
    incident_location: document.getElementById('incidentLocation').value,
    details: document.getElementById('details').value.trim(),
    tcpa_consent: document.getElementById('tcpaConsent').checked
  };

  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span>Transmitting Encrypted Lead...</span>';

  try {
    const res = await fetch('/api/leads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });

    if (!res.ok) throw new Error('Submission failed');
    const result = await res.json();

    form.reset();
    successBanner.style.display = 'block';
    successBanner.innerHTML = `
      <strong>✓ Intake Received! Certificate: ${result.trusted_form_cert}</strong><br>
      Case assigned to Georgia Senior Legal Specialist. Priority email alert dispatched.
    `;
    submitBtn.innerHTML = '<span>Submitted Successfully</span>';

    setTimeout(() => {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<span>Connect With Specialist</span>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>`;
    }, 4000);
  } catch (err) {
    alert('Error submitting form: ' + err.message);
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<span>Retry Submission</span>';
  }
}

function openCallModal(event) {
  if (event) event.preventDefault();
  document.getElementById('callModal').classList.add('active');
}

function closeCallModal() {
  document.getElementById('callModal').classList.remove('active');
}

async function startSimulatedVoiceCall() {
  closeCallModal();
  try {
    const res = await fetch('/api/vapi/simulate-call', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenarioIndex: 0 })
    });
    const result = await res.json();
    alert(`[Vapi AI Simulation Completed]\n\nCaller: ${result.callerName}\nTranscript generated & email handoff dispatched to support team!\n\nView details in Mission Control Dashboard.`);
  } catch (err) {
    alert('Call simulation failed: ' + err.message);
  }
}
