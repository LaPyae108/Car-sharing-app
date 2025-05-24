// this file must define initManageJourneyMap(canEdit)
let map, directionsService, directionsRenderer, geocoder, infoWindow;
let startMarker, endMarker, startInput, endInput;

function initManageJourneyMap(canEdit) {
  // grab the form inputs
  startInput = document.getElementById("start_location");
  endInput   = document.getElementById("end_location");

  // create the map
  map = new google.maps.Map(document.getElementById("map"), {
    center: { lat: 53.7996, lng: -1.5468 },
    zoom: 13,
  });

  directionsService = new google.maps.DirectionsService();
  directionsRenderer = new google.maps.DirectionsRenderer({ suppressMarkers: true });
  directionsRenderer.setMap(map);

  geocoder = new google.maps.Geocoder();
  infoWindow = new google.maps.InfoWindow();

  // geocode your saved addresses & place initial markers
  let pending = 0;
  function geocodeAndPlace(address, label) {
    pending++;
    geocoder.geocode({ address }, (results, status) => {
      if (status === "OK" && results[0]) {
        const loc = results[0].geometry.location;
        const mk = createMarker(loc, label, canEdit);
        if (label === "A") startMarker = mk;
        else                endMarker   = mk;
        mk.addListener("click", () => {
          if (canEdit) infoWindow.open(map, mk);
        });
        if (--pending === 0) drawRoute();
      }
    });
  }

  geocodeAndPlace(startInput.value, "A");
  geocodeAndPlace(endInput.value,   "B");

  // only wire up editing if allowed
  if (canEdit) {
    // click-to-place new markers
    map.addListener("click", (e) => {
      placeOnClick(e.latLng);
    });

    // autocomplete fields
    const startAuto = new google.maps.places.Autocomplete(startInput);
    const endAuto   = new google.maps.places.Autocomplete(endInput);

    startAuto.addListener("place_changed", () => placeFromAutocomplete(startAuto, "A"));
    endAuto  .addListener("place_changed", () => placeFromAutocomplete(endAuto,   "B"));
  }

  // create a marker (draggable if canEdit)
  function createMarker(position, label, draggable) {
    const m = new google.maps.Marker({
      position,
      map,
      label,
      draggable,
    });
    if (draggable) {
      m.addListener("dragend", () => onMarkerDrag(label, m));
    }
    return m;
  }

  // recalc route if both markers present
  function drawRoute() {
    if (!startMarker || !endMarker) return;
    directionsRenderer.set("directions", null);
    directionsService.route({
      origin:      startMarker.getPosition(),
      destination: endMarker.getPosition(),
      travelMode:  "DRIVING",
    }, (res, status) => {
      if (status === "OK") directionsRenderer.setDirections(res);
    });
  }

  // when you click map to place A or B
  function placeOnClick(latLng) {
    geocoder.geocode({ location: latLng }, (results, status) => {
      if (status==="OK" && results[0]) {
        const addr = results[0].formatted_address;
        if (!startMarker || (startMarker && endMarker)) {
          // reset A
          if (startMarker) startMarker.setMap(null);
          startMarker = createMarker(latLng, "A", true);
          startInput.value = addr;
        } else {
          // place B
          if (endMarker) endMarker.setMap(null);
          endMarker = createMarker(latLng, "B", true);
          endInput.value = addr;
        }
        drawRoute();
      }
    });
  }

  // when you drag A or B
  function onMarkerDrag(label, marker) {
    geocoder.geocode({ location: marker.getPosition() }, (results, status) => {
      if (status==="OK" && results[0]) {
        if (label==="A") startInput.value = results[0].formatted_address;
        else             endInput.value   = results[0].formatted_address;
        drawRoute();
      }
    });
  }

  // when you pick via autocomplete
  function placeFromAutocomplete(autocomplete, label) {
    const place = autocomplete.getPlace();
    if (!place.geometry) return;
    const loc = place.geometry.location;
    if (label==="A") {
      if (startMarker) startMarker.setMap(null);
      startMarker = createMarker(loc, "A", true);
      startInput.value = place.formatted_address;
    } else {
      if (endMarker) endMarker.setMap(null);
      endMarker = createMarker(loc, "B", true);
      endInput.value = place.formatted_address;
    }
    map.setCenter(loc);
    drawRoute();
  }
}
