/* MH3U Quest Notebook: write quest drafts on a phone, send them to the PC editor.
 *
 * Everything stays on the phone (localStorage). A draft is exported as a small JSON file
 * (.mh3ud) that the PC editor imports with "From phone..." on the Library page; the PC
 * editor turns it into a real quest by copying a game quest of the same map and applying
 * the draft on top of it.
 */
"use strict";

const APP_VERSION = "1.0.0";
const FORMAT = "mh3u-quest-draft";
const BUNDLE = "mh3u-quest-drafts";
const STORE = "mh3u.notebook.drafts";
const SETTINGS = "mh3u.notebook.settings";
const NATIVE = window.Android || null;

const OBJ = { hunt: 0x0001, capture: 0x0081, slay: 0x0101, small: 0x8101, deliver: 0x0002 };
const SIEGE = [20, 25, 70, 85];               // Jhen Mohran, Ceadeus and their variants
const ARRIVALS = {                            // number of monsters -> [start_param, groups, label key]
  2: [[0, [2], "arr_both"], [1, [1, 1], "arr_one_other"]],
  3: [[0, [3], "arr_all3"], [1, [1, 1, 1], "arr_one_another"], [5, [1, 2], "arr_1_2"], [6, [2, 1], "arr_2_1"]],
  4: [[0, [4], "arr_all4"], [1, [1, 1, 1, 1], "arr_one_another"], [4, [1, 2, 1], "arr_1_2_1"], [8, [2, 2], "arr_2_2"]],
  5: [[0, [5], "arr_all5"], [1, [1, 1, 1, 1, 1], "arr_one_another"]],
};

// ------------------------------------------------------------------------- texts
const T = {
  fr: {
    app: "Carnet de quêtes MH3U", my_quests: "Mes quêtes", new_quest: "＋ Nouvelle quête",
    empty: "Aucune quête pour l'instant.\nTouchez « Nouvelle quête » pour écrire la première.",
    untitled: "(quête sans nom)", tab_quest: "Quête", tab_monsters: "Monstres", tab_goal: "Objectif",
    tab_rewards: "Récompenses", tab_texts: "Textes", tab_send: "Envoyer",
    quest_name: "Nom de la quête", star: "Étoiles", hub: "Lieu", village: "Village", port: "Port",
    rank: "Rang des monstres", map: "Carte", choose_map: "Choisir la carte", time: "Temps limite", minutes: "min",
    frozen: "Chrono figé (99 min, le temps ne s'écoule pas)", money: "Zennys et points de rang",
    fee: "Frais", reward: "Récompense", hrp: "Points de rang", usual: "Valeurs habituelles",
    usual_hint: "Quêtes du jeu {g} : frais {f} z, récompense {r} z, {h} points.",
    who: "Qui peut participer, jour ou nuit", hr_min: "Rang de chasseur", any: "Tous",
    hr_n: "RC {n} ou plus", players: "Joueurs", pl4: "Jusqu'à 4 (normal)", pl1: "1 (seul)", pl2: "Jusqu'à 2",
    pl3: "Jusqu'à 3", naked: "Sans armure ni talisman", time_of_day: "Moment", day: "Jour", night: "Nuit",
    carves: "Découpes d'arène (objets comme des Méga potions au lieu des matériaux)",
    day_only: "Cette carte n'a pas de quête de nuit dans le jeu.",
    monsters: "Grands monstres", add_monster: "＋ Ajouter un monstre", no_monster: "Aucun grand monstre.",
    count: "Nombre", size: "Taille", count_hint: "arrivent l'un après l'autre",
    cards_hint: "Pour avoir deux fois le même monstre, ajoutez-le deux fois (comme dans les quêtes du jeu).", custom_size: "Autre taille (%)", strength: "Force",
    strength_auto: "Auto : {g}", remove: "Retirer", arrival: "Arrivée des monstres",
    on_map: "Va sur cette carte", needs_pack: "Pas sur cette carte dans le jeu : demande le Pack monstres (non testé)",
    siege_note: "Monstre de siège : le combat se règle sur PC (drakkar, objectif de siège).",
    goal: "Objectif de la quête", kind: "Type", k_hunt: "Chasser", k_capture: "Capturer", k_slay: "Tuer",
    k_deliver: "Livrer", k_small: "Petits monstres",
    auto_goal: "L'objectif suit les monstres : ceux du dernier groupe qui arrive doivent être vaincus.",
    item: "Objet", choose_item: "Choisir l'objet", small_mon: "Petit monstre", choose_small: "Choisir le petit monstre",
    goal_is: "Objectif", rewards: "Récompenses", rw_auto: "Automatiques", rw_mine: "Les miennes",
    rw_auto_hint: "L'éditeur PC choisira les récompenses des quêtes du jeu de même rang, avec les matériaux des monstres.",
    rw_add: "＋ Ajouter un objet", qty: "Qté", chance: "%", rw_total: "Total des chances : {n} %",
    rw_total_hint: "Les tableaux du jeu font en général 100 %.", rw_none: "Aucun objet.",
    texts: "Textes de la quête", obj_text: "Texte de l'objectif", obj_auto: "Écrire depuis l'objectif",
    sub_obj: "Sous-objectif", failure: "Conditions d'échec",
    failure_ph: "Vide : le texte de la quête copiée sur PC", client: "Client", description: "Description",
    notes: "Mes notes (ne vont pas dans le jeu)",
    lang_note: "Les textes sont mis dans les 5 langues du jeu ; l'éditeur PC permet de les traduire.",
    send: "Envoyer vers le PC", save_file: "Enregistrer le fichier…", share: "Partager…",
    send_hint: "Enregistrez le fichier dans Google Drive ou Téléchargements (câble USB), ou partagez-le. Sur le PC : page Bibliothèque, bouton « Depuis le téléphone… ».",
    check: "Vérification", all_good: "Rien à signaler : la quête est prête à être envoyée.",
    e_name: "Donnez un nom à la quête.", e_monster: "Ajoutez au moins un grand monstre.",
    e_item: "Choisissez l'objet à livrer.", e_small: "Choisissez le petit monstre.",
    w_pack: "{m} ne va pas sur {map} dans le jeu : il faudra le Pack monstres (combinaison non testée).",
    w_night: "Cette carte n'a pas de quête de nuit dans le jeu : la nuit n'y est pas testée.",
    w_rules: "Le jeu garde 2 règles au plus : choisissez deux parmi rang, joueurs et sans armure.",
    w_total: "Les chances des récompenses font {n} % (le jeu utilise en général 100 %).",
    w_siege: "{m} est un monstre de siège : finissez le réglage sur PC.",
    w_small_large: "{m} n'est pas un petit monstre.",
    menu_import: "Importer un fichier…", menu_backup: "Sauvegarder toutes les quêtes…", menu_theme_n: "Thème nuit",
    menu_theme_d: "Thème parchemin", menu_lang: "English", menu_about: "À propos",
    m_save: "Enregistrer le fichier…", m_share: "Partager…", m_dup: "Dupliquer", m_delete: "Supprimer",
    del_q: "Supprimer « {n} » ?", yes: "Oui", no: "Non", cancel: "Annuler", copy: "copie",
    saved: "Fichier enregistré.", save_err: "Le fichier n'a pas pu être enregistré.",
    imported: "{n} quête(s) importée(s).", import_err: "Ce fichier n'est pas une quête du carnet.",
    search: "Rechercher…", type_more: "Tapez pour chercher parmi {n} objets.", others: "Autres monstres",
    about: "Carnet de quêtes MH3U {v}\nCompagnon du MH3U Custom Quest Editor.\nÉcrivez vos quêtes ici, puis importez-les sur PC où elles deviennent de vraies quêtes.\nRien n'est envoyé sur Internet : tout reste sur le téléphone tant que vous ne partagez pas un fichier.",
    arr_both: "Les deux au début", arr_one_other: "L'un après l'autre", arr_all3: "Les trois au début",
    arr_one_another: "L'un après l'autre", arr_1_2: "Le premier, puis les deux autres ensemble",
    arr_2_1: "Les deux premiers ensemble, puis le dernier", arr_all4: "Les quatre au début",
    arr_1_2_1: "Le premier, puis deux ensemble, puis le dernier", arr_2_2: "Deux ensemble, puis deux ensemble",
    arr_all5: "Les cinq au début", and: " et ", none_goal: "Aucun objectif",
    ranks: ["Rang inférieur (Village)", "Rang inférieur (Port)", "Rang supérieur (Village)", "Rang supérieur (Port)", "Rang G"],
    sizes: ["Minuscule (20 %)", "Petit (40 %)", "Normal (100 %)", "Taille royale (125 %)", "Géant (200 %)"],
    classes: { "Bird Wyverns": "Wyvernes aviaires", "Flying Wyverns": "Wyvernes volantes", "Piscine Wyverns": "Wyvernes nageuses",
      "Brute Wyverns": "Wyvernes brutales", "Leviathans": "Léviathans", "Fanged Beasts": "Bêtes à crocs",
      "Fanged Wyverns": "Wyvernes à crocs", "Elder Dragons": "Dragons anciens", "Small monsters": "Petits monstres", "Other": "Autres" },
    low: "Rang inférieur", high: "Rang supérieur",
  },
  en: {
    app: "MH3U Quest Notebook", my_quests: "My quests", new_quest: "＋ New quest",
    empty: "No quest yet.\nTap \"New quest\" to write the first one.",
    untitled: "(untitled quest)", tab_quest: "Quest", tab_monsters: "Monsters", tab_goal: "Objective",
    tab_rewards: "Rewards", tab_texts: "Texts", tab_send: "Send",
    quest_name: "Quest name", star: "Stars", hub: "Hub", village: "Village", port: "Port",
    rank: "Monster rank", map: "Map", choose_map: "Choose the map", time: "Time limit", minutes: "min",
    frozen: "Frozen clock (99 min, time never runs out)", money: "Zenny and HR points",
    fee: "Fee", reward: "Reward", hrp: "HR points", usual: "Usual values",
    usual_hint: "Game quests {g}: fee {f} z, reward {r} z, {h} points.",
    who: "Who can join, day or night", hr_min: "Hunter Rank", any: "Any",
    hr_n: "HR {n} or higher", players: "Players", pl4: "Up to 4 (normal)", pl1: "1 (solo)", pl2: "Up to 2",
    pl3: "Up to 3", naked: "No armor or talismans", time_of_day: "Time of day", day: "Day", night: "Night",
    carves: "Arena carves (items such as Mega Potions instead of monster parts)",
    day_only: "This map has no night quest in the game.",
    monsters: "Large monsters", add_monster: "＋ Add a monster", no_monster: "No large monster.",
    count: "Count", size: "Size", count_hint: "arriving one after another",
    cards_hint: "To have the same monster twice, add it twice (as the game's quests do).", custom_size: "Other size (%)", strength: "Strength",
    strength_auto: "Auto: {g}", remove: "Remove", arrival: "How the monsters arrive",
    on_map: "Goes on this map", needs_pack: "Not on this map in the game: needs the Monster pack (untested)",
    siege_note: "Siege monster: the fight is set up on the PC (Dragonship, siege objective).",
    goal: "Quest objective", kind: "Type", k_hunt: "Hunt", k_capture: "Capture", k_slay: "Slay",
    k_deliver: "Deliver", k_small: "Small monsters",
    auto_goal: "The objective follows the monsters: the last group to arrive must be beaten.",
    item: "Item", choose_item: "Choose the item", small_mon: "Small monster", choose_small: "Choose the small monster",
    goal_is: "Objective", rewards: "Rewards", rw_auto: "Automatic", rw_mine: "My own",
    rw_auto_hint: "The PC editor will pick the rewards of the game's quests of the same rank, with the monsters' materials.",
    rw_add: "＋ Add an item", qty: "Qty", chance: "%", rw_total: "Total chance: {n} %",
    rw_total_hint: "The game's tables usually add up to 100 %.", rw_none: "No item.",
    texts: "Quest texts", obj_text: "Objective text", obj_auto: "Write it from the objective",
    sub_obj: "Sub-objective", failure: "Failure conditions",
    failure_ph: "Empty: the text of the quest copied on the PC", client: "Client", description: "Description",
    notes: "My notes (not put in the game)",
    lang_note: "The texts go into the game's 5 languages; the PC editor can translate them.",
    send: "Send to the PC", save_file: "Save as a file…", share: "Share…",
    send_hint: "Save the file to Google Drive or Downloads (USB cable), or share it. On the PC: Library page, \"From phone...\" button.",
    check: "Check", all_good: "Nothing to report: the quest is ready to send.",
    e_name: "Give the quest a name.", e_monster: "Add at least one large monster.",
    e_item: "Choose the item to deliver.", e_small: "Choose the small monster.",
    w_pack: "{m} does not go on {map} in the game: it will need the Monster pack (untested combination).",
    w_night: "This map has no night quest in the game: night is untested there.",
    w_rules: "The game holds 2 rules at most: choose two of Hunter Rank, players and no armor.",
    w_total: "The reward chances add up to {n} % (the game usually uses 100 %).",
    w_siege: "{m} is a siege monster: finish the set-up on the PC.",
    w_small_large: "{m} is not a small monster.",
    menu_import: "Import a file…", menu_backup: "Back up every quest…", menu_theme_n: "Night theme",
    menu_theme_d: "Parchment theme", menu_lang: "Français", menu_about: "About",
    m_save: "Save as a file…", m_share: "Share…", m_dup: "Duplicate", m_delete: "Delete",
    del_q: "Delete \"{n}\"?", yes: "Yes", no: "No", cancel: "Cancel", copy: "copy",
    saved: "File saved.", save_err: "The file could not be saved.",
    imported: "{n} quest(s) imported.", import_err: "This file is not a notebook quest.",
    search: "Search…", type_more: "Type to search {n} items.", others: "Other monsters",
    about: "MH3U Quest Notebook {v}\nCompanion of the MH3U Custom Quest Editor.\nWrite your quests here, then import them on the PC, where they become real quests.\nNothing is sent over the Internet: everything stays on the phone until you share a file.",
    arr_both: "Both at the start", arr_one_other: "One after the other", arr_all3: "All three at the start",
    arr_one_another: "One after another", arr_1_2: "The first one, then the other two together",
    arr_2_1: "The first two together, then the last one", arr_all4: "All four at the start",
    arr_1_2_1: "The first one, then two together, then the last one", arr_2_2: "Two together, then two together",
    arr_all5: "All five at the start", and: " and ", none_goal: "No objective",
    ranks: ["Low rank (Village)", "Low rank (Port)", "High rank (Village)", "High rank (Port)", "G rank"],
    sizes: ["Tiny (20 %)", "Small (40 %)", "Normal (100 %)", "King Size (125 %)", "Giant (200 %)"],
    classes: {}, low: "Low Rank", high: "High Rank",
  },
};

// ------------------------------------------------------------------------ state
let settings = load(SETTINGS, null) || {};
if (!settings.lang) settings.lang = (navigator.language || "fr").toLowerCase().startsWith("fr") ? "fr" : "en";
if (settings.night === undefined) settings.night = !!(window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches);
let drafts = load(STORE, {}) || {};
let view = "list", cur = null, tab = "quest";
const overlays = [];
const MONS = new Map(DATA.monsters.map(m => [m.id, m]));
const ITEMS = new Map(DATA.items.map(i => [i[0], i]));
const MAPS = new Map(DATA.maps.map(m => [m.id, m]));

function load(key, dflt) {
  try { const s = localStorage.getItem(key); return s ? JSON.parse(s) : dflt; } catch (e) { return dflt; }
}
function store(key, val) {
  try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) { toast("Storage error: " + e); }
}
let saveTimer = null;
function persist(now) {
  if (cur) cur.updated = new Date().toISOString();
  clearTimeout(saveTimer);
  if (now) store(STORE, drafts); else saveTimer = setTimeout(() => store(STORE, drafts), 250);
}
function t(key, vars) {
  let s = (T[settings.lang] && T[settings.lang][key]);
  if (s === undefined) s = T.en[key];
  if (s === undefined) s = key;
  if (vars && typeof s === "string") for (const k in vars) s = s.split("{" + k + "}").join(vars[k]);
  return s;
}
const L = () => settings.lang;
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (sel, root) => (root || document).querySelector(sel);
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const k in (attrs || {})) {
    const v = attrs[k];
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else if (k === "style") el.style.cssText = v;
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false)
    el.appendChild(typeof kid === "string" || typeof kid === "number" ? document.createTextNode(String(kid)) : kid);
  return el;
}

// ----------------------------------------------------------------- game tables
const monName = id => { const m = MONS.get(id); return m ? m[L()] || m.en : "#" + id; };
const itemName = id => { const i = ITEMS.get(id); return i ? (L() === "fr" ? i[2] : i[1]) : "#" + id; };
const mapName = id => { const m = MAPS.get(id); return m ? m[L()] || m.en : "?"; };
const isLarge = m => m && m.cls !== "Small monsters" && m.cls !== "Other";
const groupsOf = hub => DATA.groups.filter(g => g.hub === hub);
function groupFor(hub, star) {             // the game's group of this hub with the nearest star rank
  let best = null;
  for (const g of groupsOf(hub)) if (!best || Math.abs(g.star - star) < Math.abs(best.star - star)) best = g;
  return best;
}
function groupLabel(g) {
  if (!g) return "";
  if (g.hub === "Village") return `${t("village")} ${g.star}★`;
  const r = g.star <= 2 ? t("low") : g.star <= 5 ? t("high") : `G${g.star - 5}★`;
  return `${t("port")} ${g.star}★ (${r})`;
}
function rankFor(hub, star) {              // what the game's own quests use (checked on the EU quests)
  if (hub === "Village") return star <= 5 ? 0 : 2;
  return star <= 2 ? 1 : star <= 5 ? 3 : 4;
}
function monSprite(id) {
  const m = MONS.get(id), n = m ? m.icon : null, el = h("div", { class: "mon" });
  if (n === null || n === undefined) { el.style.backgroundImage = "none"; return el; }
  const c = DATA.sprites.monster_columns;
  el.style.backgroundPosition = `-${(n % c) * 54}px -${Math.floor(n / c) * 54}px`;
  return el;
}
function itemSprite(id) {
  const i = ITEMS.get(id), n = i ? i[3] : null, el = h("div", { class: "item" });
  if (n === null || n === undefined) { el.style.backgroundImage = "none"; return el; }
  const c = DATA.sprites.item_columns;
  el.style.backgroundPosition = `-${(n % c) * 44}px -${Math.floor(n / c) * 44}px`;
  return el;
}
const mapImg = id => h("img", { class: "mapimg", src: `img/maps/map${String(id).padStart(2, "0")}_160.png`, alt: "" });

// ---------------------------------------------------------------------- drafts
function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }
function newDraft() {
  const g = groupFor("Village", 1), now = new Date().toISOString();
  return { format: FORMAT, version: 1, app: "MH3U Quest Notebook " + APP_VERSION, id: uid(), created: now, updated: now,
    lang: L(), name: "", client: "", description: "", objective_text: "", objective_auto: true, sub_objective: "",
    failure: "", star: 1, hub: "Village", rank: 0, rank_auto: true, map: 1, time: g ? g.time : 50,
    fee: g ? g.fee : 0, reward: g ? g.reward : 0, hrp: g ? g.hrp : 0, money_auto: true,
    hr: null, players: 4, naked: false, night: false, arena_carves: false,
    monsters: [], arrival: 0, objective: { kind: "hunt", item: 0, em: 0, count: 1 },
    rewards: { auto: true, items: [] }, notes: "" };
}
function onStarHub(d) {
  const g = groupFor(d.hub, d.star);
  if (d.money_auto && g) { d.fee = g.fee; d.reward = g.reward; d.hrp = g.hrp; if (d.time !== 99) d.time = g.time; }
  if (d.rank_auto) d.rank = rankFor(d.hub, d.star);
}
const largeMons = d => d.monsters.filter(m => m.em);
function arrivalGroups(d) {
  const n = largeMons(d).length, opts = ARRIVALS[n];
  if (!opts) return n ? [n] : [];
  const o = opts.find(a => a[0] === d.arrival) || opts[0];
  return o[1];
}
function huntTargets(d) {                // [(em, total)] as the PC editor derives them (waves.derive)
  const mons = largeMons(d);
  if (!mons.length) return [];
  if (mons.length === 1) return [[mons[0].em, Math.max(1, mons[0].count)]];
  const groups = arrivalGroups(d), last = mons.slice(mons.length - groups[groups.length - 1]);
  let targets = [];
  for (const m of last) if (!targets.includes(m.em)) targets.push(m.em);
  targets = targets.slice(-2);
  return targets.map(em => [em, mons.filter(m => m.em === em).reduce((a, m) => a + Math.max(1, m.count), 0)]);
}
function countName(n, name) {
  if (L() === "fr") return `${n} ${name}`;
  return n <= 1 ? (("AEIOU".includes(name[0].toUpperCase()) ? "an " : "a ") + name) : `${n} ${name}`;
}
function objectiveSentence(d) {
  const o = d.objective, verb = t("k_" + o.kind);
  if (o.kind === "deliver") return o.item ? `${verb} ${countName(Math.max(1, o.count), itemName(o.item))}` : t("none_goal");
  if (o.kind === "small") return o.em ? `${t("k_slay")} ${o.count} ${monName(o.em)}` : t("none_goal");
  const mons = largeMons(d);
  if (!mons.length) return t("none_goal");
  const targets = huntTargets(d);
  const species = [...new Set(mons.map(m => m.em))];
  const pairs = species.every(em => targets.some(x => x[0] === em))
    ? species.map(em => [em, mons.filter(m => m.em === em).reduce((a, m) => a + Math.max(1, m.count), 0)])
    : targets;
  const names = pairs.map(([em, n]) => countName(n, monName(em)));
  return verb + " " + (names.length > 1 ? names.slice(0, -1).join(", ") + t("and") + names[names.length - 1] : names[0]);
}
function refreshObjectiveText(d) { if (d.objective_auto) d.objective_text = objectiveSentence(d); }

function issues(d) {
  const out = [];                                 // [level, text]
  if (!d.name.trim()) out.push(["e", t("e_name")]);
  const k = d.objective.kind;
  if (["hunt", "capture", "slay"].includes(k) && !largeMons(d).length) out.push(["e", t("e_monster")]);
  if (k === "deliver" && !d.objective.item) out.push(["e", t("e_item")]);
  if (k === "small") {
    if (!d.objective.em) out.push(["e", t("e_small")]);
    else if (isLarge(MONS.get(d.objective.em))) out.push(["w", t("w_small_large", { m: monName(d.objective.em) })]);
  }
  for (const em of new Set(largeMons(d).map(m => m.em))) {
    const m = MONS.get(em);
    if (m && !m.maps.includes(d.map)) out.push(["w", t("w_pack", { m: monName(em), map: mapName(d.map) })]);
    if (SIEGE.includes(em)) out.push(["w", t("w_siege", { m: monName(em) })]);
  }
  if (d.night && DATA.day_only_maps.includes(d.map)) out.push(["w", t("w_night")]);
  if (d.hr && d.players !== 4 && d.naked) out.push(["w", t("w_rules")]);
  if (!d.rewards.auto && d.rewards.items.length) {
    const tot = d.rewards.items.reduce((a, r) => a + (+r.chance || 0), 0);
    if (tot !== 100) out.push(["w", t("w_total", { n: tot })]);
  }
  return out;
}

// --------------------------------------------------------------------- history
// Every screen above the list (editor, picker, dialog) is a history entry, so Android's back
// button (WebView.goBack) and the header's back arrow close them one by one.
function pushScreen(kind) { history.pushState({ kind }, ""); }
let afterPop = null;                              // run once the screen on top is closed
window.addEventListener("popstate", () => {
  if (overlays.length) overlays.pop().remove();
  else if (view === "edit") { persist(true); showList(); }
  const fn = afterPop; afterPop = null;
  if (fn) fn();
});
function closeTop(fn) { afterPop = typeof fn === "function" ? fn : null; history.back(); }
function addOverlay(el) { document.body.appendChild(el); overlays.push(el); pushScreen("overlay"); }

// ---------------------------------------------------------------------- chrome
function applyTheme() {
  document.documentElement.classList.toggle("night", !!settings.night);
  document.documentElement.lang = L();
}
function setHeader(title, back) {
  $("#title").textContent = title;
  $("#back").classList.toggle("hidden", !back);
}
function toast(msg) {
  const el = h("div", { class: "toast" }, msg);
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2600);
}
function dialog(title, options, body) {          // options: [label, sub, fn, cls]
  const box = h("div", { class: "dialog" }, title ? h("h2", null, title) : null, body || null);
  for (const [label, sub, fn, cls] of options) {
    box.appendChild(h("button", { class: "btn opt " + (cls || ""), onclick: () => closeTop(fn) },
      h("b", null, label), sub ? h("span", { class: "muted" }, sub) : null));
  }
  const bg = h("div", { class: "dialog-bg", onclick: e => { if (e.target === bg) closeTop(); } }, box);
  addOverlay(bg);
}
function askNumber(title, value, min, max, fn) {
  const input = numInput(value, min, max, () => {});
  dialog(title, [["OK", null, () => { const v = parseInt(input.value, 10); if (!isNaN(v)) fn(Math.max(min, Math.min(max, v))); else changed(true); }],
                 [t("cancel"), null, () => changed(true)]], h("div", { class: "row" }, input));
  setTimeout(() => input.focus(), 50);
}
function confirmBox(text, fn) { dialog(text, [[t("yes"), null, fn, "danger"], [t("no"), null, null]]); }

// ------------------------------------------------------------------------ list
function showList() {
  view = "list"; cur = null;
  setHeader(t("app"), false);
  $("#tabs").classList.add("hidden");
  const main = $("#main");
  main.innerHTML = "";
  const list = Object.values(drafts).sort((a, b) => (b.updated || "").localeCompare(a.updated || ""));
  main.appendChild(h("h2", null, t("my_quests")));
  if (!list.length) main.appendChild(h("div", { class: "empty" }, ...t("empty").split("\n").map(l => h("p", null, l))));
  for (const d of list) {
    const first = largeMons(d)[0];
    const icon = first ? monSprite(first.em) : h("div", { class: "qicon" }, "📜");
    const bad = issues(d).some(i => i[0] === "e");
    const mons = [...new Set(largeMons(d).map(m => monName(m.em)))].join(", ");
    main.appendChild(h("div", { class: "card quest", onclick: () => openDraft(d.id) }, icon,
      h("div", { class: "info" },
        h("div", { class: "name" }, d.name || t("untitled")),
        h("div", { class: "muted" }, `${"★".repeat(Math.min(d.star, 10))}  ·  ${mapName(d.map)}${mons ? "  ·  " + mons : ""}`),
        bad ? h("div", { class: "warn" }, "● " + issues(d).find(i => i[0] === "e")[1]) : null),
      h("button", { class: "btn small", onclick: e => { e.stopPropagation(); draftMenu(d); } }, "⋯")));
  }
  main.appendChild(h("button", { class: "btn accent fab", onclick: () => { const d = newDraft(); drafts[d.id] = d; persist(true); openDraft(d.id); } }, t("new_quest")));
}
function draftMenu(d) {
  dialog(d.name || t("untitled"), [
    [t("m_save"), null, () => saveFile(d)],
    [t("m_share"), null, () => shareFile(d)],
    [t("m_dup"), null, () => duplicate(d)],
    [t("m_delete"), null, () => confirmBox(t("del_q", { n: d.name || t("untitled") }), () => remove(d)), "danger"],
  ]);
}
function duplicate(d) {
  const c = JSON.parse(JSON.stringify(d));
  c.id = uid(); c.created = c.updated = new Date().toISOString();
  c.name = (d.name || t("untitled")) + " (" + t("copy") + ")";
  drafts[c.id] = c; persist(true);
  if (view === "list") showList(); else toast(c.name);
}
function remove(d) {
  delete drafts[d.id]; persist(true);
  if (view === "edit") closeTop(); else showList();
}

// ---------------------------------------------------------------------- editor
const TABS = [["quest", "📜"], ["monsters", "🐉"], ["goal", "🎯"], ["rewards", "💰"], ["texts", "✒️"], ["send", "📤"]];
function openDraft(id) {
  cur = drafts[id]; if (!cur) return;
  view = "edit"; tab = "quest";
  pushScreen("edit");
  renderEdit();
}
function renderEdit() {
  setHeader(cur.name || t("untitled"), true);
  const nav = $("#tabs");
  nav.classList.remove("hidden");
  nav.innerHTML = "";
  const errs = issues(cur).some(i => i[0] === "e");
  for (const [k, ic] of TABS) {
    nav.appendChild(h("button", { class: tab === k ? "on" : "", onclick: () => { tab = k; renderEdit(); window.scrollTo(0, 0); } },
      h("span", { class: "ic" }, ic), h("span", null, t("tab_" + k), k === "send" && errs ? h("span", { class: "dot" }) : null)));
  }
  const main = $("#main");
  main.innerHTML = "";
  ({ quest: tabQuest, monsters: tabMonsters, goal: tabGoal, rewards: tabRewards, texts: tabTexts, send: tabSend })[tab](main);
}
function changed(rerender) {
  refreshObjectiveText(cur);
  persist();
  if (rerender) { const y = window.scrollY; renderEdit(); window.scrollTo(0, y); }
  else setHeader(cur.name || t("untitled"), true);
}
function field(label, input, extra) {
  return h("div", { class: "row" }, h("label", { class: "l" }, label), h("div", { class: "grow" }, input), extra || null);
}
function textInput(key, opts) {
  opts = opts || {};
  const el = h(opts.area ? "textarea" : "input", { type: "text", placeholder: opts.ph || "", rows: opts.rows || null,
    maxlength: opts.max || null });
  el.value = cur[key] || "";
  el.addEventListener("input", () => { cur[key] = el.value; if (opts.onchange) opts.onchange(); changed(false); });
  return el;
}
function numInput(value, min, max, fn) {
  const el = h("input", { type: "number", min, max, inputmode: "numeric", value });
  el.addEventListener("change", () => {
    let v = parseInt(el.value, 10); if (isNaN(v)) v = min;
    v = Math.max(min, Math.min(max, v)); el.value = v; fn(v);
  });
  return el;
}
function seg(options, value, fn) {
  return h("div", { class: "seg" }, options.map(([v, label]) =>
    h("button", { class: v === value ? "on" : "", onclick: () => fn(v) }, label)));
}
function select(options, value, fn) {
  const el = h("select", null, options.map(([v, label]) => h("option", { value: JSON.stringify(v), selected: v === value }, label)));
  el.addEventListener("change", () => fn(JSON.parse(el.value)));
  return el;
}

function tabQuest(main) {
  const d = cur;
  main.appendChild(h("div", { class: "card" },
    field(t("quest_name"), textInput("name", { max: 60 })),
    h("div", { class: "row" }, h("label", { class: "l" }, t("hub")),
      seg([["Village", t("village")], ["Port", t("port")]], d.hub, v => {
        d.hub = v; if (d.hub === "Village" && d.star > 9) d.star = 9; onStarHub(d); changed(true); })),
    h("div", { class: "row" }, h("label", { class: "l" }, t("star")),
      h("div", { class: "stars" }, Array.from({ length: d.hub === "Village" ? 9 : 10 }, (_, i) => i + 1).map(n =>
        h("button", { class: n === d.star ? "on" : "", onclick: () => { d.star = n; onStarHub(d); changed(true); } }, n)))),
    field(t("rank"), select(t("ranks").map((l, i) => [i, l]), d.rank, v => { d.rank = v; d.rank_auto = false; changed(true); })),
  ));
  main.appendChild(h("div", { class: "card" },
    h("h2", null, t("map")),
    h("button", { class: "pick", onclick: pickMap }, mapImg(d.map), h("div", { class: "grow" }, h("b", null, mapName(d.map)),
      h("div", { class: "sub" }, t("choose_map")))),
    field(t("time"), numInput(d.time, 1, 99, v => { d.time = v; changed(true); }), h("span", { class: "muted" }, t("minutes"))),
    h("label", { class: "check" }, h("input", { type: "checkbox", checked: d.time === 99, onchange: e => {
      const g = groupFor(d.hub, d.star); d.time = e.target.checked ? 99 : (g ? g.time : 50); changed(true); } }), t("frozen")),
  ));
  const g = groupFor(d.hub, d.star);
  const money = (key) => numInput(d[key], 0, key === "hrp" ? 99999 : 999999, v => { d[key] = v; d.money_auto = false; changed(true); });
  main.appendChild(h("div", { class: "card" },
    h("h2", null, t("money")),
    field(t("fee"), money("fee"), h("span", { class: "muted" }, "z")),
    field(t("reward"), money("reward"), h("span", { class: "muted" }, "z")),
    field(t("hrp"), money("hrp")),
    g ? h("div", { class: "muted" }, t("usual_hint", { g: groupLabel(g), f: g.fee, r: g.reward, h: g.hrp })) : null,
    h("div", { class: "row" }, h("button", { class: "btn small", onclick: () => { d.money_auto = true; onStarHub(d); changed(true); } }, t("usual"))),
  ));
  const dayOnly = DATA.day_only_maps.includes(d.map);
  main.appendChild(h("div", { class: "card" },
    h("h2", null, t("who")),
    field(t("time_of_day"), seg([[false, t("day")], [true, t("night")]], d.night, v => { d.night = v; changed(true); })),
    dayOnly ? h("div", { class: d.night ? "warn" : "muted" }, t("day_only")) : null,
    field(t("hr_min"), select([[null, t("any")]].concat(DATA.hr.map(n => [n, t("hr_n", { n })])), d.hr, v => { d.hr = v; changed(true); })),
    field(t("players"), select([[4, t("pl4")], [1, t("pl1")], [2, t("pl2")], [3, t("pl3")]], d.players, v => { d.players = v; changed(true); })),
    h("label", { class: "check" }, h("input", { type: "checkbox", checked: d.naked, onchange: e => { d.naked = e.target.checked; changed(true); } }), t("naked")),
    h("label", { class: "check" }, h("input", { type: "checkbox", checked: d.arena_carves, onchange: e => { d.arena_carves = e.target.checked; changed(false); } }), t("carves")),
    (d.hr && d.players !== 4 && d.naked) ? h("div", { class: "warn" }, t("w_rules")) : null,
  ));
}

function tabMonsters(main) {
  const d = cur;
  const card = h("div", { class: "card" }, h("h2", null, t("monsters")));
  main.appendChild(card);
  if (!d.monsters.length) card.appendChild(h("p", { class: "muted" }, t("no_monster")));
  const g = groupFor(d.hub, d.star);
  d.monsters.forEach((m, i) => {
    const info = MONS.get(m.em);
    const onMap = info && info.maps.includes(d.map);
    const sizeOpts = DATA.sizes.map(([_l, s], k) => [s, t("sizes")[k]]);
    if (!sizeOpts.some(o => o[0] === m.size)) sizeOpts.push([m.size, m.size + " %"]);
    sizeOpts.push(["custom", t("custom_size") + "…"]);
    const strOpts = [[null, t("strength_auto", { g: g ? `${t(g.hub === "Village" ? "village" : "port")} ${g.star}★` : "" })]].concat(DATA.groups.map(x => [x.key, groupLabel(x)]));
    main.appendChild(h("div", { class: "card moncard" },
      h("div", { class: "head" }, monSprite(m.em),
        h("div", { class: "grow" }, h("b", null, monName(m.em)),
          h("span", { class: onMap ? "muted" : "warn" }, onMap ? t("on_map") : t("needs_pack")),
          SIEGE.includes(m.em) ? h("div", { class: "warn" }, t("siege_note")) : null),
        h("button", { class: "btn small", onclick: () => pickMonster(em => { m.em = em; changed(true); }) }, "⇄")),
      d.monsters.length > 1 ? null : h("div", { class: "row" }, h("label", { class: "l" }, t("count")),
        h("div", { class: "stepper" },
          h("button", { onclick: () => { m.count = Math.max(1, m.count - 1); changed(true); } }, "−"),
          h("span", { class: "count" }, m.count),
          h("button", { onclick: () => { m.count = Math.min(5, m.count + 1); changed(true); } }, "+")),
        m.count > 1 ? h("span", { class: "muted" }, t("count_hint")) : null),
      field(t("size"), select(sizeOpts, m.size, v => {
        if (v === "custom") askNumber(t("custom_size"), m.size, 1, 255, s => { m.size = s; changed(true); });
        else { m.size = v; changed(true); }
      })),
      field(t("strength"), select(strOpts, m.strength || null, v => { m.strength = v; changed(true); })),
      h("div", { class: "btns" },
        i > 0 ? h("button", { class: "btn small", onclick: () => { [d.monsters[i - 1], d.monsters[i]] = [d.monsters[i], d.monsters[i - 1]]; changed(true); } }, "▲") : null,
        i < d.monsters.length - 1 ? h("button", { class: "btn small", onclick: () => { [d.monsters[i + 1], d.monsters[i]] = [d.monsters[i], d.monsters[i + 1]]; changed(true); } }, "▼") : null,
        h("button", { class: "btn small danger", onclick: () => { d.monsters.splice(i, 1); fixArrival(d); changed(true); } }, t("remove"))),
    ));
  });
  if (d.monsters.length < 5)
    main.appendChild(h("button", { class: "btn accent wide", onclick: () => pickMonster(em => {
      // the game's quests give each monster its own card: copies of one card become cards too
      if (d.monsters.length === 1 && d.monsters[0].count > 1) {
        const first = d.monsters[0], n = Math.min(4, first.count);
        d.monsters = Array.from({ length: n }, () => Object.assign({}, first, { count: 1 }));
      }
      if (d.monsters.length < 5) d.monsters.push({ em, count: 1, size: 100, strength: null });
      fixArrival(d); changed(true); }) }, t("add_monster")));
  if (d.monsters.length > 1) main.appendChild(h("p", { class: "muted" }, t("cards_hint")));
  const opts = ARRIVALS[largeMons(d).length];
  if (opts) main.appendChild(h("div", { class: "card", style: "margin-top:12px" }, h("h2", null, t("arrival")),
    select(opts.map(o => [o[0], t(o[2])]), d.arrival, v => { d.arrival = v; changed(true); })));
}
function fixArrival(d) {
  const opts = ARRIVALS[largeMons(d).length];
  if (!opts || !opts.some(o => o[0] === d.arrival)) d.arrival = 0;
}

function tabGoal(main) {
  const d = cur, o = d.objective;
  const card = h("div", { class: "card" }, h("h2", null, t("goal")),
    seg([["hunt", t("k_hunt")], ["capture", t("k_capture")], ["slay", t("k_slay")], ["deliver", t("k_deliver")], ["small", t("k_small")]],
      o.kind, v => { o.kind = v; if (v === "deliver" || v === "small") o.count = Math.max(1, o.count); changed(true); }));
  main.appendChild(card);
  if (["hunt", "capture", "slay"].includes(o.kind)) {
    card.appendChild(h("p", { class: "muted" }, t("auto_goal")));
  } else if (o.kind === "deliver") {
    card.appendChild(h("button", { class: "pick", onclick: () => pickItem(id => { o.item = id; changed(true); }) },
      o.item ? itemSprite(o.item) : h("div", { class: "qicon" }, "?"),
      h("div", { class: "grow" }, h("b", null, o.item ? itemName(o.item) : t("choose_item")), h("div", { class: "sub" }, t("item")))));
    card.appendChild(field(t("count"), numInput(o.count, 1, 99, v => { o.count = v; changed(true); })));
  } else {
    card.appendChild(h("button", { class: "pick", onclick: () => pickMonster(em => { o.em = em; changed(true); }, true) },
      o.em ? monSprite(o.em) : h("div", { class: "qicon" }, "?"),
      h("div", { class: "grow" }, h("b", null, o.em ? monName(o.em) : t("choose_small")), h("div", { class: "sub" }, t("small_mon")))));
    card.appendChild(field(t("count"), numInput(o.count, 1, 99, v => { o.count = v; changed(true); })));
  }
  card.appendChild(h("div", { class: "row" }, h("b", null, t("goal_is") + " : "), h("span", null, objectiveSentence(d))));
}

function tabRewards(main) {
  const d = cur, r = d.rewards;
  const card = h("div", { class: "card" }, h("h2", null, t("rewards")),
    seg([[true, t("rw_auto")], [false, t("rw_mine")]], r.auto, v => { r.auto = v; changed(true); }));
  main.appendChild(card);
  if (r.auto) { card.appendChild(h("p", { class: "muted" }, t("rw_auto_hint"))); return; }
  if (!r.items.length) card.appendChild(h("p", { class: "muted" }, t("rw_none")));
  const total = () => r.items.reduce((a, x) => a + (+x.chance || 0), 0);
  const totLab = h("div", { class: "muted" });
  const showTot = () => { const n = total(); totLab.textContent = t("rw_total", { n }) + (n !== 100 ? "  —  " + t("rw_total_hint") : ""); totLab.className = n === 100 ? "ok" : "warn"; };
  r.items.forEach((x, i) => {
    const qty = h("input", { type: "number", min: 1, max: 99, value: x.qty, inputmode: "numeric" });
    qty.addEventListener("change", () => { x.qty = Math.max(1, Math.min(99, parseInt(qty.value, 10) || 1)); qty.value = x.qty; changed(false); });
    const ch = h("input", { type: "number", min: 1, max: 100, value: x.chance, inputmode: "numeric" });
    ch.addEventListener("input", () => { x.chance = Math.max(0, Math.min(100, parseInt(ch.value, 10) || 0)); showTot(); changed(false); });
    card.appendChild(h("div", { class: "reward" }, itemSprite(x.item),
      h("div", { class: "grow" }, h("div", null, itemName(x.item)),
        h("div", { class: "row" }, h("span", { class: "muted" }, t("qty")), qty, h("span", { class: "muted" }, t("chance")), ch)),
      h("button", { class: "btn small danger", onclick: () => { r.items.splice(i, 1); changed(true); } }, "✕")));
  });
  card.appendChild(totLab); showTot();
  if (r.items.length < 32)
    main.appendChild(h("button", { class: "btn accent wide", onclick: () => pickItem(id => {
      r.items.push({ item: id, qty: 1, chance: Math.max(1, 100 - total()) }); changed(true); }) }, t("rw_add")));
}

function tabTexts(main) {
  const d = cur;
  const objIn = textInput("objective_text", { area: true, rows: 2, onchange: () => { d.objective_auto = false; } });
  main.appendChild(h("div", { class: "card" }, h("h2", null, t("texts")),
    field(t("quest_name"), textInput("name", { max: 60 })),
    h("div", { class: "row" }, h("label", { class: "l" }, t("obj_text"))), objIn,
    h("div", { class: "row" }, h("button", { class: "btn small", onclick: () => { d.objective_auto = true; changed(true); } }, t("obj_auto"))),
    h("div", { class: "row" }, h("label", { class: "l" }, t("sub_obj"))), textInput("sub_objective", { area: true, rows: 2 }),
    h("div", { class: "row" }, h("label", { class: "l" }, t("failure"))), textInput("failure", { area: true, rows: 2, ph: t("failure_ph") }),
    field(t("client"), textInput("client", { max: 60 })),
    h("div", { class: "row" }, h("label", { class: "l" }, t("description"))), textInput("description", { area: true, rows: 7 }),
    h("p", { class: "muted" }, t("lang_note")),
  ));
  main.appendChild(h("div", { class: "card" }, h("h2", null, t("notes")), textInput("notes", { area: true, rows: 4 })));
}

function tabSend(main) {
  const d = cur, list = issues(d);
  main.appendChild(h("div", { class: "card" }, h("h2", null, t("check")),
    h("div", { class: "issues" }, list.length ? list.map(([lv, text]) => h("div", { class: lv === "e" ? "danger" : "warn" }, (lv === "e" ? "✖ " : "▲ ") + text))
      : h("div", { class: "ok" }, "✔ " + t("all_good")))));
  main.appendChild(h("div", { class: "card" }, h("h2", null, t("send")),
    h("p", { class: "muted" }, t("send_hint")),
    h("div", { class: "btns" },
      h("button", { class: "btn accent", onclick: () => saveFile(d) }, t("save_file")),
      h("button", { class: "btn", onclick: () => shareFile(d) }, t("share")))));
}

// --------------------------------------------------------------------- pickers
function picker(title, groups, onpick, opts) {
  opts = opts || {};
  const input = h("input", { type: "text", placeholder: t("search") });
  const list = h("div", { class: "list" });
  const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  function fill() {
    const q = norm(input.value.trim());
    list.innerHTML = "";
    let shown = 0;
    for (const [gname, entries] of groups) {
      const hits = q ? entries.filter(e => norm(e.search).includes(q)) : entries;
      if (!hits.length) continue;
      if (opts.limit && !q && shown >= opts.limit) break;
      if (gname) list.appendChild(h("div", { class: "grp" }, gname));
      for (const e of hits) {
        if (opts.limit && shown >= opts.limit) break;
        list.appendChild(h("button", { class: "pick" + (e.on ? " on" : ""), onclick: () => closeTop(() => onpick(e.key)) },
          e.icon(), h("div", { class: "grow" }, h("div", null, e.name), e.sub ? h("div", { class: "sub" }, e.sub) : null)));
        shown++;
      }
    }
    if (opts.limit && !q) list.appendChild(h("p", { class: "muted" }, t("type_more", { n: opts.total })));
  }
  input.addEventListener("input", fill);
  const el = h("div", { class: "overlay" },
    h("header", { class: "bar" }, h("button", { onclick: () => closeTop() }, "‹"), h("div", { class: "title" }, title)),
    h("div", { class: "search" }, input), list);
  addOverlay(el);
  fill();
}
function pickMap() {
  picker(t("choose_map"), [[null, DATA.maps.map(m => ({ key: m.id, name: mapName(m.id), search: m.en + " " + m.fr,
    on: m.id === cur.map, icon: () => mapImg(m.id) }))]], id => {
    cur.map = id; if (cur.night && DATA.day_only_maps.includes(id)) cur.night = false; changed(true); });
}
function pickMonster(fn, small) {
  const mk = m => ({ key: m.id, name: monName(m.id), search: m.en + " " + m.fr,
    sub: (T.fr.classes[m.cls] && L() === "fr" ? T.fr.classes[m.cls] : m.cls) + (m.threat ? "  " + "★".repeat(m.threat) : ""),
    icon: () => monSprite(m.id) });
  const byThreat = (a, b) => (a.threat - b.threat) || monName(a.id).localeCompare(monName(b.id));
  let groups;
  if (small) {
    groups = [[null, DATA.monsters.filter(m => m.cls === "Small monsters").sort(byThreat).map(mk)]];
  } else {
    const large = DATA.monsters.filter(isLarge);
    groups = [[t("on_map") + " — " + mapName(cur.map), large.filter(m => m.maps.includes(cur.map)).sort(byThreat).map(mk)],
              [t("others") + " — " + t("needs_pack"), large.filter(m => !m.maps.includes(cur.map)).sort(byThreat).map(mk)]];
  }
  picker(small ? t("choose_small") : t("add_monster").replace("＋ ", ""), groups, fn);
}
function pickItem(fn) {
  const entries = DATA.items.map(i => ({ key: i[0], name: L() === "fr" ? i[2] : i[1], search: i[1] + " " + i[2], icon: () => itemSprite(i[0]) }));
  picker(t("choose_item"), [[null, entries]], fn, { limit: 60, total: entries.length });
}

// ------------------------------------------------------------- files (native)
function fileName(d) {
  const base = (d.name || "quest").replace(/[\\/:*?"<>|\r\n\t]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 50) || "quest";
  return base + ".mh3ud";
}
function exportText(d) {
  const out = JSON.parse(JSON.stringify(d));
  out.format = FORMAT; out.version = 1; out.app = "MH3U Quest Notebook " + APP_VERSION; out.lang = d.lang || L();
  out.objective.type = OBJ[out.objective.kind];
  return JSON.stringify(out, null, 1);
}
let pending = null;                               // what to do when the native side answers
window.nativeEvent = function (kind) {
  const p = pending; pending = null;
  if (kind === "saved") toast(t("saved"));
  else if (kind === "error") toast(t("save_err"));
  else if (kind === "opened" && NATIVE) importText(NATIVE.takeOpened());
  if (p) p(kind);
};
function download(name, text) {
  const a = h("a", { href: URL.createObjectURL(new Blob([text], { type: "application/octet-stream" })), download: name });
  document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}
function saveFile(d) {
  persist(true);
  if (NATIVE) NATIVE.saveFile(fileName(d), exportText(d)); else download(fileName(d), exportText(d));
}
function shareFile(d) {
  persist(true);
  const name = fileName(d), text = exportText(d);
  if (NATIVE) { if (!NATIVE.shareFile(name, text)) toast(t("save_err")); return; }
  try {
    const f = new File([text], name, { type: "application/octet-stream" });
    if (navigator.canShare && navigator.canShare({ files: [f] })) { navigator.share({ files: [f], title: name }); return; }
  } catch (e) { /* fall back to a download */ }
  download(name, text);
}
function backupAll() {
  const all = Object.values(drafts);
  const text = JSON.stringify({ format: BUNDLE, version: 1, app: "MH3U Quest Notebook " + APP_VERSION,
    drafts: all.map(d => JSON.parse(exportText(d))) }, null, 1);
  const name = "MH3U quests " + new Date().toISOString().slice(0, 10) + ".mh3ud";
  if (NATIVE) NATIVE.saveFile(name, text); else download(name, text);
}
function openFile() {
  if (NATIVE) NATIVE.openFile(); else $("#filein").click();
}
$("#filein").addEventListener("change", e => {
  const f = e.target.files[0]; if (!f) return;
  f.text().then(importText); e.target.value = "";
});
function importText(text) {
  let data;
  try { data = JSON.parse(text); } catch (e) { toast(t("import_err")); return; }
  const list = data && data.format === BUNDLE ? data.drafts : [data];
  let n = 0;
  for (const d of list || []) {
    if (!d || d.format !== FORMAT || typeof d !== "object") continue;
    const base = newDraft();
    const merged = Object.assign(base, d);
    merged.objective = Object.assign(base.objective, d.objective || {});
    merged.rewards = Object.assign({ auto: true, items: [] }, d.rewards || {});
    merged.monsters = Array.isArray(d.monsters) ? d.monsters.filter(m => MONS.has(m.em)) : [];
    const same = drafts[merged.id];
    if (same && same.updated === merged.updated) continue;     // already here
    if (same) merged.id = uid();
    drafts[merged.id] = merged; n++;
  }
  persist(true);
  toast(n ? t("imported", { n }) : t("import_err"));
  if (view === "list") showList();
}

// ------------------------------------------------------------------------ menu
$("#menu").addEventListener("click", () => {
  if (view === "edit") { draftMenu(cur); return; }
  dialog(t("app"), [
    [t("menu_import"), null, openFile],
    [t("menu_backup"), null, backupAll],
    [settings.night ? t("menu_theme_d") : t("menu_theme_n"), null, () => { settings.night = !settings.night; store(SETTINGS, settings); applyTheme(); }],
    [t("menu_lang"), null, () => { settings.lang = L() === "fr" ? "en" : "fr"; store(SETTINGS, settings); applyTheme(); showList(); }],
    [t("menu_about"), null, () => dialog(null, [["OK", null, null]], h("div", null, ...t("about", { v: APP_VERSION }).split("\n").map(l => h("p", null, l))))],
  ]);
});
$("#back").addEventListener("click", () => closeTop());

applyTheme();
showList();
