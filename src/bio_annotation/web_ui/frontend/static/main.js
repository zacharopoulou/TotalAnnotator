"use strict";

(() => {
  const popup = document.getElementById("entity-popup");
  if (!popup) return;

  const titleEl = popup.querySelector("#entity-popup-title");
  const infoEl = popup.querySelector(".entity-popup-info");
  const sourcesEl = popup.querySelector(".entity-popup-sources");
  const closeBtn = popup.querySelector(".entity-popup-close");

  const ENTITY_TYPE_LABELS = {
    gene: "Gene / protein",
    disease: "Disease",
    drug: "Chemical / drug",
    species: "Species",
    variant: "Variant / mutation",
    cell_line: "Cell line",
    unknown: "Entity",
  };

  const ANNOTATOR_LABELS = {
    pubtator3: "PubTator3",
    bern2: "BERN2",
    flair: "Flair / HunFlair",
  };

  function databaseLink(canonicalId) {
    if (!canonicalId) return null;
    const id = String(canonicalId).trim();
    const meshMatch = id.match(/^mesh:(.+)$/i);
    if (meshMatch) {
      return {
        label: "View in MeSH",
        url: `https://meshb.nlm.nih.gov/record/ui?ui=${encodeURIComponent(meshMatch[1])}`,
      };
    }
    const geneMatch = id.match(/^ncbi[_-]?gene:(.+)$/i);
    if (geneMatch) {
      return {
        label: "View in NCBI Gene",
        url: `https://www.ncbi.nlm.nih.gov/gene/${encodeURIComponent(geneMatch[1])}`,
      };
    }
    const taxMatch = id.match(/^ncbi[_-]?taxonomy:(.+)$/i);
    if (taxMatch) {
      return {
        label: "View in NCBI Taxonomy",
        url: `https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=${encodeURIComponent(taxMatch[1])}`,
      };
    }
    const snpMatch = id.match(/^dbsnp:(.+)$/i);
    if (snpMatch) {
      return {
        label: "View in dbSNP",
        url: `https://www.ncbi.nlm.nih.gov/snp/${encodeURIComponent(snpMatch[1])}`,
      };
    }
    const chebiMatch = id.match(/^chebi:(.+)$/i);
    if (chebiMatch) {
      return {
        label: "View in ChEBI",
        url: `https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:${encodeURIComponent(chebiMatch[1])}`,
      };
    }
    const drugbankMatch = id.match(/^drugbank:(.+)$/i);
    if (drugbankMatch) {
      return {
        label: "View in DrugBank",
        url: `https://go.drugbank.com/drugs/${encodeURIComponent(drugbankMatch[1])}`,
      };
    }
    const cellosaurusMatch = id.match(/^(?:cellosaurus|cvcl):(.+)$/i);
    if (cellosaurusMatch) {
      const cvcl = cellosaurusMatch[1].startsWith("CVCL_") ? cellosaurusMatch[1] : `CVCL_${cellosaurusMatch[1]}`;
      return {
        label: "View in Cellosaurus",
        url: `https://www.cellosaurus.org/${encodeURIComponent(cvcl)}`,
      };
    }
    const omimMatch = id.match(/^omim:(.+)$/i);
    if (omimMatch) {
      return {
        label: "View in OMIM",
        url: `https://www.omim.org/entry/${encodeURIComponent(omimMatch[1])}`,
      };
    }
    return null;
  }

  function appendInfo(label, value, options = {}) {
    if (value === null || value === undefined || value === "") return;
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    if (options.link) {
      const link = document.createElement("a");
      link.href = options.link;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = value;
      dd.appendChild(link);
    } else {
      dd.textContent = value;
    }
    infoEl.appendChild(dt);
    infoEl.appendChild(dd);
  }

  function annotatorLabel(name) {
    return ANNOTATOR_LABELS[name] || name;
  }

  function entityTypeLabel(type) {
    return ENTITY_TYPE_LABELS[type] || type || "Entity";
  }

  function renderSourceRow(name, hits) {
    const row = document.createElement("div");
    row.className = "entity-popup-source";

    const heading = document.createElement("div");
    heading.className = "entity-popup-source-name";
    heading.textContent = annotatorLabel(name);
    row.appendChild(heading);

    const list = document.createElement("ul");
    list.className = "entity-popup-source-hits";
    for (const hit of hits) {
      const li = document.createElement("li");
      const parts = [];
      if (hit.canonical_id) parts.push(`ID: ${hit.canonical_id}`);
      if (hit.canonical_name) parts.push(`name: ${hit.canonical_name}`);
      if (typeof hit.confidence === "number") {
        parts.push(`confidence: ${hit.confidence.toFixed(3)}`);
      }
      if (parts.length === 0) parts.push("matched");
      li.textContent = parts.join(" · ");
      list.appendChild(li);
    }
    row.appendChild(list);
    return row;
  }

  function openPopup(mark) {
    let data;
    try {
      data = JSON.parse(mark.dataset.entity || "{}");
    } catch (err) {
      console.error("Failed to parse entity data", err);
      return;
    }

    titleEl.textContent = entityTypeLabel(data.entity_type);
    infoEl.innerHTML = "";
    sourcesEl.innerHTML = "";

    appendInfo("Keyword", data.keyword);
    appendInfo("Canonical name", data.canonical_name);

    const link = databaseLink(data.canonical_id);
    appendInfo(
      "Canonical id",
      data.canonical_id,
      link ? { link: link.url } : {},
    );

    const sources = data.by_source || {};
    const sortedSources = Object.keys(sources).sort();
    if (sortedSources.length === 0) {
      const note = document.createElement("p");
      note.className = "entity-popup-empty";
      note.textContent = "No annotator details available.";
      sourcesEl.appendChild(note);
    } else {
      for (const sourceName of sortedSources) {
        sourcesEl.appendChild(renderSourceRow(sourceName, sources[sourceName]));
      }
    }

    popup.classList.remove("hidden");
    popup.setAttribute("aria-hidden", "false");
    closeBtn.focus();
  }

  function closePopup() {
    popup.classList.add("hidden");
    popup.setAttribute("aria-hidden", "true");
  }

  document.addEventListener("click", (event) => {
    const mark = event.target.closest("mark.entity");
    if (mark) {
      event.preventDefault();
      openPopup(mark);
      return;
    }
    if (event.target === popup) {
      closePopup();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      const mark = event.target.closest && event.target.closest("mark.entity");
      if (mark) {
        event.preventDefault();
        openPopup(mark);
      }
    }
    if (event.key === "Escape" && !popup.classList.contains("hidden")) {
      closePopup();
    }
  });

  closeBtn.addEventListener("click", closePopup);
})();
