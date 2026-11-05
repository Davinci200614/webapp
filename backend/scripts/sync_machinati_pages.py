"""Copy original MACHINATI documents intact, adapting only integration/bug fixes.
Run explicitly from backend: python -m scripts.sync_machinati_pages --source ../../MACHINATI/frontend
Generated documents are committed artifacts; normal build/runtime needs no source repo.
"""
import argparse
from pathlib import Path
import re
import hashlib
import json


def adapt(source, kind):
    text=source
    private=kind!='catalogue'
    route='/cooperative' if kind=='cooperative' else '/operations'
    text=text.replace('<html lang="fr">',f'<html lang="fr" data-operator="{str(private).lower()}" data-login-path="{route}"'+(' class="awaiting-auth"' if private else '')+'>')
    text=text.replace('</head>', '<style>.awaiting-auth body{visibility:hidden}</style><script src="./bridge.js"></script></head>')
    text=text.replace('const apiBaseUrl = new URLSearchParams(window.location.search).get("apiBaseUrl") || "";', 'const apiBaseUrl = "";')
    text=text.replace('<script>','<script>\nwindow.machinatiReady.then(ready => { if (!ready) return;')
    text=text.replace('  </script>','\n});\n  </script>')
    # Expose notices to the bridge without exposing domain data.
    text=text.replace('    function showNotice(message) {','    window.machinatiNotice = showNotice;\n    function showNotice(message) {')
    if kind=='catalogue':
        text=text.replace('"/?view=cooperative"','"/cooperative"').replace('"/?view=operations"','"/operations"')
        text=text.replace('      combine_harvester: "Moissonneuse",','      combine_harvester: "Moissonneuse",\n      harvester: "Moissonneuse", baler: "Presse à foin", sprayer: "Pulvérisateur", irrigation_pump: "Irrigation",')
        text=text.replace('Boolean(machine.available));','Boolean(machine.available) && !machine.reserved_for_own_use);')
        text=text.replace('return `https://wa.me/?text=${encodeURIComponent(message)}`;', 'return `https://wa.me/${window.machinatiWhatsApp}?text=${encodeURIComponent(message)}`;')
        text=text.replace('      window.open(`https://wa.me/?text=${encodeURIComponent(message)}`, "_blank", "noopener,noreferrer");','      if (!window.machinatiWhatsApp) { showNotice("Le numéro WhatsApp du service n’est pas encore configuré."); return; }\n      window.open(`https://wa.me/${window.machinatiWhatsApp}?text=${encodeURIComponent(message)}`, "_blank", "noopener,noreferrer");')
        # Exact card appearance, but connect its original booking dialog.
        text=text.replace('href="${rentalWhatsAppUrl(machine)}"', 'href="${rentalWhatsAppUrl(machine)}" data-modal="booking" data-machine="${machine.id}"')
        text=text.replace('openModal(openButton.dataset.modal);','openModal(openButton.dataset.modal, openButton.dataset.machine);')
        text=text.replace('      mobileMenu.setAttribute("aria-expanded", "false");','      const expanded = mobileMenu.getAttribute("aria-expanded") !== "true";\n      mobileMenu.setAttribute("aria-expanded", String(expanded));\n      document.getElementById("navLinks").classList.toggle("open", expanded);')
        text=text.replace('Prototype de démonstration : aucun renseignement n\'est transmis à un serveur.', 'Votre message sera préparé dans WhatsApp. Envoyez-le pour contacter l’équipe.')
        # Retain original modal layout but use actual hourly inventory rates.
        text=text.replace('MAD / jour','MAD / h').replace('Date de début','Date souhaitée').replace('Réserver cette machine','Demander cette machine')
        text=text.replace('<label for="rentalDays">Durée</label><select id="rentalDays" name="days"><option value="1">1 jour</option><option value="2">2 jours</option><option value="3">3 jours</option><option value="5">5 jours</option><option value="7">7 jours</option></select>', '<label for="rentalDays">Durée (heures)</label><input id="rentalDays" name="days" type="number" min="1" step="1" value="1" required>')
        text=text.replace('1 jour</span>','1 heure</span>').replace('${data.get("days")} jour(s).','${data.get("days")} heure(s).')
        text=text.replace('      if (estimate) estimate.remove();', '      if (estimate && !machine?.hasPrice) estimate.remove();')
        text=text.replace('      if (form.id === "ownerForm") {', '      if (!window.machinatiWhatsApp) { showNotice("Le numéro WhatsApp du service n’est pas encore configuré."); return; }\n      if (form.id === "ownerForm") {')
        # Dynamic inventory text must never become HTML in the original modal.
        text=text.replace('${machine.title}</strong>', '${escapeHtml(machine.title)}</strong>').replace('${machine.city} · ${machine.price', '${escapeHtml(machine.city)} · ${machine.price')
        text=text.replace('loadFilterOptions();', '''loadFilterOptions();
        document.getElementById("categoryFilters").innerHTML = '<button class="category-chip active" type="button" data-category="">Tout le matériel</button>' + [...new Set(machines.map(m => m.category))].map(category => `<button class="category-chip" type="button" data-category="${escapeHtml(category)}">${escapeHtml(category)}</button>`).join('');''')
        marker='    const mobileMenu = document.getElementById("mobileMenu");'
        text=text.replace(marker,'''    modal.addEventListener("input", event => {
      if (event.target.id !== "rentalDays") return;
      const form = document.getElementById("bookingForm");
      const hours = Number(event.target.value);
      const total = document.getElementById("estimateTotal");
      if (total) total.textContent = (Number(form.dataset.price) * hours).toLocaleString("fr-FR");
      const unit = document.getElementById("estimateDays");
      if (unit) unit.textContent = `${hours} heure(s)`;
    });
''' + marker)
        text=text.replace('    function openModal(kind, machineId) {', '    let previousFocus = null;\n    function openModal(kind, machineId) {\n      previousFocus = document.activeElement;')
        text=text.replace('      document.body.style.overflow = "";', '      document.body.style.overflow = "";\n      previousFocus?.focus();')
        text=text.replace('    const mobileMenu = document.getElementById("mobileMenu");', '''    modal.addEventListener("keydown", event => {
      if (event.key !== "Tab") return;
      const fields = modal.querySelectorAll('button:not(:disabled), input, select, textarea, a[href]');
      const first = fields[0], last = fields[fields.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    const mobileMenu = document.getElementById("mobileMenu");''')
    else:
        # Reserved machines must not inflate availability summaries.
        text=text.replace('Boolean(machine.available)).length', 'Boolean(machine.available) && !machine.reserved_for_own_use).length')
        if kind=='cooperative':
            text=text.replace('id="toggleMachineForm" type="button" disabled title="La création de machines n\'est pas encore disponible dans l\'API">Gestion des machines bientôt', 'id="toggleMachineForm" type="button" onclick="window.top.location.href=\'/machines\'">Gérer les machines')
            text=text.replace('machine.available ?','machine.available && !machine.reserved_for_own_use ?')
        else:
            text=text.replace('machine.available ?', 'machine.available && !machine.reserved_for_own_use ?')
            text=text.replace('      if (matches.length && !matches.some', '''      if (!matches.length) {
        selectedRequestId = null;
        for (const id of ["detailId", "detailMachine", "detailClient", "detailDates", "detailRegion", "detailCooperative", "detailPriority", "detailStatus"]) document.getElementById(id).textContent = "—";
        document.getElementById("detailHistory").replaceChildren();
        document.getElementById("confirmButton").disabled = true;
        document.getElementById("advanceButton").disabled = true;
        return;
      }
      if (matches.length && !matches.some''')
            text=text.replace('const typeLabels = { tractor:', 'const typeLabels = { harvester: "Moissonneuse", irrigation_pump: "Irrigation", baler: "Presse à foin", sprayer: "Pulvérisateur", tractor:')
            text=text.replace('const machine = machines.find((item) => item.machine_type === machineType && (!payload.location || item.location === payload.location));','const machine = record.matching_machines?.[0];')
    return text


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    args=parser.parse_args()
    target=Path(__file__).resolve().parents[2]/'frontend'/'public'/'assets'/'machinati'
    target.mkdir(parents=True,exist_ok=True)
    manifest={}
    for kind,path in [('catalogue',args.source/'public'/'catalogue.html'),('cooperative',args.source/'cooperative.html'),('operations',args.source/'equipe-machinati.html')]:
        (target/(kind+'.html')).write_text(adapt(path.read_text(),kind))
        manifest[kind]={'source':str(path),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'original_style_sha256':hashlib.sha256(re.search(r'<style>(.*?)</style>',path.read_text(),re.S)[1].encode()).hexdigest()}
        print('Synced',kind)
    (target/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

if __name__=='__main__': main()
