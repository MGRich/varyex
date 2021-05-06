var HEADERNAME = "aryex"

setInterval(() => {
    el = document.getElementById("header");
    tx = document.getElementById("header-text")
    if (window.scrollY !== 0) {
        el.style.backgroundColor = "rgba(24, 20, 30, 70%)";
        if (tx.textContent.length !== 0) {
            tx.textContent = tx.textContent.slice(0, -1)
        }
    }
    else {
        el.style.backgroundColor = "rgba(24, 20, 30, 100%)";
        if (tx.textContent.length !== HEADERNAME.length) {
            tx.textContent = HEADERNAME.slice(0, tx.textContent.length + 1)
        }
    }
    
}, 50);

window.onclick = function(event)  {
    if (!event.target.matches('#header-dropdown')) {

    }
}