console.log("Car Sharing App JavaScript loaded");

document.addEventListener("DOMContentLoaded", () => {
  // Display fixed journey info
  const bookingInfo = {
    name: "Journey Booking",
    price: "25.00"
  };

  // Show booking info in summary box
  const itemContainer = document.getElementById("item-container");
  if (itemContainer) {
    itemContainer.textContent = `${bookingInfo.name} - Price: £${bookingInfo.price}`;
  }

  // ✅ Define the button *before* using it
  const stripeCheckoutButton = document.getElementById("stripe-checkout-button");
  if (stripeCheckoutButton) {
    stripeCheckoutButton.addEventListener("click", () => {
      const notesInput = document.getElementById("passenger-notes");
      const notes = notesInput ? notesInput.value : "";

      fetch("/create-checkout-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          price: bookingInfo.price,
          name: bookingInfo.name,
          notes: notes
        })
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.error) {
            console.error("Stripe session error:", data.error);
          } else {
            const stripe = Stripe('pk_test_51R4TU3FleNCLelKmAHfwLQalp4RGhYYYmrQDB9KulWvSBQ5lads4HBLIuvdQ7zyEPfzxHmbioO05dQS82gG6jZhk00qr1hctdX');
            stripe.redirectToCheckout({ sessionId: data.sessionId });
          }
        })
        .catch((error) => console.error("Checkout error:", error));
    });
  }
});
