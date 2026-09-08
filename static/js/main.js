// main.js
//
// Dashboard "All expenses" ledger: click a column header to sort the rows by
// that column; click the same header again to reverse. Pagination is handled
// server-side (?page=N), so this sorts the rows on the page you are viewing.
// The footer Total row lives in <tfoot> and is never reordered.

(function () {
  "use strict";

  var table = document.querySelector(".ledger-table");
  if (!table || !table.tHead || !table.tBodies[0]) {
    return;
  }

  var tbody = table.tBodies[0];
  var headers = Array.prototype.slice.call(table.tHead.rows[0].cells);

  // Value used to compare a row on a given column. A cell may carry an explicit
  // data-sort attribute (used for amounts, so "₹1,200.00" sorts as 1200);
  // otherwise the trimmed visible text is used.
  function valueFor(row, columnIndex, type) {
    var cell = row.cells[columnIndex];
    if (!cell) {
      return type === "number" ? 0 : "";
    }
    var raw = cell.dataset.sort != null ? cell.dataset.sort : cell.textContent;
    raw = raw.trim();
    if (type === "number") {
      var parsed = parseFloat(raw);
      return isNaN(parsed) ? 0 : parsed;
    }
    return raw.toLowerCase();
  }

  function sortRows(columnIndex, type, ascending) {
    var rows = Array.prototype.slice.call(tbody.rows);
    var direction = ascending ? 1 : -1;
    rows.sort(function (a, b) {
      var av = valueFor(a, columnIndex, type);
      var bv = valueFor(b, columnIndex, type);
      if (av < bv) { return -direction; }
      if (av > bv) { return direction; }
      return 0;
    });
    var fragment = document.createDocumentFragment();
    rows.forEach(function (row) { fragment.appendChild(row); });
    tbody.appendChild(fragment);
  }

  headers.forEach(function (th, columnIndex) {
    var type = th.dataset.type || "text";

    th.setAttribute("role", "button");
    th.setAttribute("tabindex", "0");
    th.setAttribute("aria-sort", "none");

    function activate() {
      var ascending = th.getAttribute("aria-sort") !== "ascending";

      headers.forEach(function (other) {
        other.setAttribute("aria-sort", "none");
        other.classList.remove("is-sorted-asc", "is-sorted-desc");
      });

      th.setAttribute("aria-sort", ascending ? "ascending" : "descending");
      th.classList.add(ascending ? "is-sorted-asc" : "is-sorted-desc");

      sortRows(columnIndex, type, ascending);
    }

    th.addEventListener("click", activate);
    th.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " " || event.key === "Spacebar") {
        event.preventDefault();
        activate();
      }
    });
  });
})();
