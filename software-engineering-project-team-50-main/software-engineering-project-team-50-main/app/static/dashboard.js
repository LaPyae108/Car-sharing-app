document.addEventListener("DOMContentLoaded", function () {
  // Sidebar accordion
  document.querySelectorAll(".nav-title").forEach(title => {
    title.addEventListener("click", () => {
      const content = title.nextElementSibling;
      content.classList.toggle("hidden");
    });
  });

  // Enter-to-send in chat inputs
  document.querySelectorAll('[id^="chat-input-"]').forEach(input => {
    input.addEventListener("keypress", e => {
      if (e.key === "Enter") {
        const bookingId = input.id.split("-").pop();
        sendMessage("booking", bookingId);
      }
    });
  });
});

function toggleModal(type, id) {
  const modal = document.getElementById(`modal-${type}-${id}`);
  if (!modal) {
    console.warn(`Modal not found: modal-${type}-${id}`);
    return;
  }
  modal.classList.toggle("hidden");
}
// expose for inline onclicks
window.toggleModal = toggleModal;

// Chat sending
function sendMessage(type, id) {
  const input   = document.getElementById(`chat-input-${id}`);
  const history = document.getElementById(`chat-box-${id}`);
  const message = input.value.trim();
  if (!message) return;

  const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  fetch("/send_message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ booking_id: id, message })
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      history.insertAdjacentHTML("beforeend", `
        <div class="text-right">
          <div class="inline-block bg-blue-100 p-2 rounded-md">
            ${message} <span class="ml-2 text-xs text-gray-500">${now}</span>
          </div>
        </div>`);
      input.value = "";
      history.scrollTop = history.scrollHeight;
    }
  })
  .catch(() => console.error("Failed to send message"));
}

// Rating
const _ratings = {};

function setRating(itemId, rating) {
  _ratings[itemId] = rating;
  for (let i = 1; i <= 5; i++) {
    const star = document.getElementById(`star-${itemId}-${i}`);
    star.classList.toggle("text-yellow-400", i <= rating);
    star.classList.toggle("text-gray-400",  i >  rating);
  }
  document.getElementById(`stars-${itemId}`).dataset.rating = rating;
}

function submitRating(itemId) {
  const container = document.getElementById(`stars-${itemId}`);
  const rating    = parseInt(container.dataset.rating, 10);
  const comment   = document.getElementById(`rating-comment-${itemId}`).value;

  if (!rating) {
    return alert("Please select a rating.");
  }

  fetch("/submit_rating", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      booking_id:     itemId,
      rating_score:   rating,
      rating_comment: comment
    })
  })
  .then(r => r.json())
  .then(json => {
    if (json.success) {
      for (let i = 1; i <= 5; i++) {
        document.getElementById(`star-${itemId}-${i}`)
                .classList.add("cursor-default");
      }
      document.getElementById(`rating-comment-${itemId}`).disabled = true;
      document.getElementById(`thankyou-${itemId}`).classList.remove("hidden");
    } else {
      alert(json.error || "Error submitting rating.");
    }
  })
  .catch(() => alert("Network error. Please try again."));
}

function showTab(tab) {
  document.querySelectorAll('.tab-content').forEach(t => t.classList.add('hidden'));
  document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('bg-blue-50', 'bg-blue-100'));

  const selectedTab = document.getElementById('tab-' + tab);
  const selectedNav = document.getElementById('nav-' + tab);

  if (selectedTab) selectedTab.classList.remove('hidden');
  if (selectedNav) selectedNav.classList.add('bg-blue-50');
}


// Auto-remove flash messages after 5 seconds
window.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    const flash = document.getElementById('flash-messages');
    if (flash) flash.remove();
  }, 5000);
});