export function addWarning(name, severity) {
    const list = document.getElementById("warnings_list");
    const item = document.createElement("div");
    item.className = "warning-item";
    if (severity === "amber") {
        item.classList.add("warning-amber");
    }
    if (severity === "red") {
        item.classList.add("warning-red");
    }
    item.textContent = name;
    item.onclick = () => {
        item.classList.add("acknowledged");
    };
    // newest at top
    list.insertBefore(item, list.firstChild);
}
