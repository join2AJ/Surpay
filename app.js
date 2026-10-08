// Phase A (concierge MVP): the search form collects a lead; a human runs the lookup
// against county surplus lists and emails the result. Set SURPAY_INTAKE_URL to any
// endpoint that accepts a JSON POST (Formspree, a Google Apps Script, your own API).
const SURPAY_INTAKE_URL = "";

document.getElementById("yr").textContent = new Date().getFullYear();

const form = document.getElementById("check");
const msg = form.querySelector(".form-msg");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  msg.className = "form-msg";

  if (!form.checkValidity()) {
    msg.textContent = "Please fill in your name, previous address, state and email, and tick the consent box.";
    msg.classList.add("err");
    return;
  }

  const data = Object.fromEntries(new FormData(form));
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;

  try {
    if (SURPAY_INTAKE_URL) {
      const res = await fetch(SURPAY_INTAKE_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ ...data, submittedAt: new Date().toISOString() }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } else {
      console.warn("SURPAY_INTAKE_URL is not set; submission was not sent.", data);
    }
    form.reset();
    msg.textContent = "Thanks. We’re searching county records for your name and will email your results within 2 business days.";
    msg.classList.add("ok");
  } catch (err) {
    msg.textContent = "Something went wrong sending your search. Please try again in a moment.";
    msg.classList.add("err");
  } finally {
    button.disabled = false;
  }
});
