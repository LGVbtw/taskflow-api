"""Streamlit dashboard that reads tender data directly from the Django ORM."""
from __future__ import annotations

import json
import html
import os
import sys
import textwrap
from datetime import date, datetime, time
from itertools import islice
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Sequence, Tuple

import pandas as pd
import streamlit as st

try:
    from streamlit_sortables import sort_items

    HAS_SORTABLE = True
except ImportError:  # pragma: no cover - optional dependency
    sort_items = None  # type: ignore
    HAS_SORTABLE = False

# Ensure project root is importable and Django is configured before importing models
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # noqa: E402

django.setup()

from django.db.models import Min, Max, Q  # noqa: E402
from django.utils import timezone  # noqa: E402
from django.core.management import call_command  # noqa: E402

from tenders.models import Tender  # noqa: E402

st.set_page_config(page_title="Tenders dashboard", layout="wide")
STREAMLIT_HAS_MODAL = hasattr(st, "modal")
AUTO_BOOTSTRAP_ENABLED = os.getenv("TASKFLOW_AUTO_BOOTSTRAP", "1").lower() not in {"0", "false", "no", "off"}
try:
    BOOTSTRAP_PAGES = max(1, int(os.getenv("TASKFLOW_BOOTSTRAP_PAGES", "1")))
except ValueError:
    BOOTSTRAP_PAGES = 1

THEME_CSS = """
<style>
:root {
    --tf-bg: radial-gradient(circle at top, #0d1423, #05070d 60%);
    --tf-surface: rgba(13, 20, 35, 0.75);
    --tf-glass: rgba(255, 255, 255, 0.08);
    --tf-border: rgba(255, 255, 255, 0.12);
    --tf-text: #e8edf7;
    --tf-muted: #9ba9c9;
    --tf-accent: linear-gradient(135deg, #7f5dff, #22d3ee);
}

body {
    background: #05070d;
    color: var(--tf-text);
    font-family: "Space Grotesk", "Inter", -apple-system, BlinkMacSystemFont, sans-serif;
}

.stApp {
    background: var(--tf-bg);
}

[data-testid="stSidebar"] {
    background: rgba(5, 7, 13, 0.85);
    border-right: 1px solid rgba(255,255,255,0.05);
    backdrop-filter: blur(12px);
}

.ambient-glow {
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: -1;
}

.ambient-glow::before,
.ambient-glow::after {
    content: "";
    position: absolute;
    width: 420px;
    height: 420px;
    border-radius: 50%;
    filter: blur(120px);
    opacity: 0.4;
}

.ambient-glow::before {
    background: #7f5dff;
    top: -120px;
    left: 10%;
}

.ambient-glow::after {
    background: #22d3ee;
    bottom: -160px;
    right: 5%;
}

.hero-v2 {
    background: var(--tf-surface);
    border: 1px solid var(--tf-border);
    border-radius: 24px;
    padding: 2rem;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 1.5rem;
    position: relative;
    overflow: hidden;
    box-shadow: 0 25px 80px rgba(0,0,0,0.45);
}

.hero-v2::after {
    content: "";
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at top right, rgba(127,93,255,0.35), transparent 45%);
    pointer-events: none;
}

.hero-title {
    font-size: 2rem;
    margin: 0 0 0.4rem;
}

.hero-lede {
    color: var(--tf-muted);
    margin: 0;
}

.cta-row {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin-top: 1.25rem;
}

.cta-primary {
    background: var(--tf-accent);
    color: #05070d;
    font-weight: 600;
    padding: 0.75rem 1.6rem;
    border-radius: 999px;
    text-decoration: none;
}

.cta-secondary {
    border: 1px solid var(--tf-border);
    padding: 0.75rem 1.6rem;
    border-radius: 999px;
    color: var(--tf-text);
    text-decoration: none;
}

.metric-stack {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
}

.metric-card {
    background: var(--tf-glass);
    border: 1px solid var(--tf-border);
    border-radius: 16px;
    padding: 1rem;
    backdrop-filter: blur(16px);
}

.metric-card span {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--tf-muted);
}

.metric-card strong {
    font-size: 1.8rem;
    display: block;
}

.stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
    margin: 1.25rem 0;
}

.stat-card {
    background: var(--tf-glass);
    border-radius: 18px;
    padding: 1.2rem;
    border: 1px solid transparent;
    background-image: linear-gradient(var(--tf-glass), var(--tf-glass)), var(--tf-accent);
    background-origin: border-box;
    background-clip: padding-box, border-box;
    color: #05070d;
}

.stat-label {
    color: #05070daa;
    font-size: 0.75rem;
    letter-spacing: 0.05em;
}

.stat-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: #05070d;
}

.board-columns {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 1rem;
    margin-top: 1rem;
}

.board-column {
    background: rgba(255,255,255,0.03);
    border-radius: 18px;
    border: 1px solid var(--tf-border);
    padding: 1rem;
    min-height: 280px;
}

.board-column h3 {
    letter-spacing: 0.15em;
    font-size: 0.75rem;
    margin: 0 0 0.8rem;
    text-transform: uppercase;
    color: var(--tf-muted);
}

.board-card {
    background: rgba(5, 7, 13, 0.65);
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.08);
    padding: 0.9rem;
    margin-bottom: 0.7rem;
    box-shadow: 0 18px 32px rgba(5,7,13,0.45);
}

.board-card h4 {
    margin: 0 0 0.4rem;
    font-size: 1rem;
}

.card-meta {
    font-size: 0.8rem;
    color: var(--tf-muted);
}

.detail-card {
    background: rgba(255,255,255,0.04);
    border-radius: 18px;
    border: 1px solid var(--tf-border);
    padding: 1rem 1.2rem;
    margin-bottom: 1rem;
}

.stat-helper {
    color: rgba(5, 7, 13, 0.75);
}

.chip {
    background: rgba(255,255,255,0.1);
    border-radius: 999px;
    padding: 0.25rem 0.8rem;
    font-size: 0.8rem;
}

.chip-inline {
    display: inline-block;
    margin-top: 0.4rem;
    margin-right: 0.35rem;
    font-size: 0.72rem;
    opacity: 0.85;
}
</style>
"""

st.markdown(THEME_CSS, unsafe_allow_html=True)
st.markdown("<div class='ambient-glow'></div>", unsafe_allow_html=True)

if "show_backlog_modal" not in st.session_state:
    st.session_state["show_backlog_modal"] = False
if "board_status" not in st.session_state:
    st.session_state["board_status"] = {}


def _html_block(fragment: str) -> str:
    """Normalize multiline HTML to avoid markdown code blocks."""
    return textwrap.dedent(fragment).strip()


@st.cache_resource(show_spinner=False)
def bootstrap_database(pages: int = BOOTSTRAP_PAGES) -> None:
    """Run migrations and ensure tenders table has data (Streamlit Cloud bootstrap)."""
    call_command("migrate", interactive=False)
    call_command("fetch_tenders", pages=pages)


if AUTO_BOOTSTRAP_ENABLED:
    bootstrap_database()


def _ensure_aware(target: datetime) -> datetime:
    """Return a timezone-aware datetime aligned with Django's settings."""
    if timezone.is_naive(target):
        return timezone.make_aware(target, timezone.get_current_timezone())
    return target


@st.cache_data(ttl=60)
def load_filter_metadata() -> Dict[str, Iterable]:
    qs = Tender.objects.all()
    categories = sorted(filter(None, qs.values_list("category", flat=True).distinct()))
    procedures = sorted(filter(None, qs.values_list("procedure", flat=True).distinct()))
    regions = sorted(filter(None, qs.values_list("region", flat=True).distinct()))
    departments = sorted(filter(None, qs.values_list("department", flat=True).distinct()))
    agg = qs.aggregate(min_deadline=Min("deadline_at"), max_deadline=Max("deadline_at"))
    return {
        "count": qs.count(),
        "categories": categories,
        "procedures": procedures,
        "regions": regions,
        "departments": departments,
        "min_deadline": agg["min_deadline"],
        "max_deadline": agg["max_deadline"],
    }


def _apply_filters(filters: Dict[str, str]) -> Iterable[Tender]:
    qs = Tender.objects.all()
    keyword = filters.get("keyword")
    if keyword:
        query = Q(title__icontains=keyword) | Q(buyer_name__icontains=keyword) | Q(buyer_location__icontains=keyword)
        qs = qs.filter(query)
    for field in ("category", "procedure", "region", "department"):
        value = filters.get(field)
        if value:
            qs = qs.filter(**{field: value})
    start: date | None = filters.get("start_date")
    end: date | None = filters.get("end_date")
    if start:
        start_dt = _ensure_aware(datetime.combine(start, time.min))
        qs = qs.filter(deadline_at__gte=start_dt)
    if end:
        end_dt = _ensure_aware(datetime.combine(end, time.max))
        qs = qs.filter(deadline_at__lte=end_dt)
    ordering = filters.get("ordering") or "deadline_at"
    qs = qs.order_by(ordering, "id")
    limit = filters.get("limit") or 200
    return qs[: int(limit)]


@st.cache_data(ttl=60)
def build_dataframe(filters: Dict[str, str]) -> pd.DataFrame:
    rows = []
    for tender in _apply_filters(filters):
        rows.append(
            {
                "ID": tender.id,
                "Titre": tender.title,
                "Acheteur": tender.buyer_name,
                "Localisation": tender.buyer_location,
                "Procédure": tender.procedure,
                "Catégorie": tender.category,
                "Région": tender.region,
                "Département": tender.department,
                "Date limite": tender.deadline_at,
                "Liens": json.dumps(tender.notice_links or {}, ensure_ascii=False),
            }
        )
    return pd.DataFrame(rows)


KANBAN_DIMENSIONS = {
    "Procédure": "Procédure",
    "Catégorie": "Catégorie",
    "Région": "Région",
    "Département": "Département",
}

BOARD_STAGES = [
    "Backlog",
    "Sélectionné pour le développement",
    "En cours",
    "Terminé",
]


def _format_datetime(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Non renseignée"
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, str):
        return value
    try:
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        localized = timezone.localtime(value)
    except Exception:
        return str(value)
    return localized.strftime("%d %b %Y %H:%M")


def render_hero(meta: Dict[str, Iterable], df: pd.DataFrame) -> None:
    total_db = meta.get("count", 0)
    filtered = len(df)
    unique_regions = int(df["Région"].nunique()) if not df.empty else 0
    unique_proc = int(df["Procédure"].nunique()) if not df.empty else 0
    st.markdown(
        _html_block(
            f"""
            <section class="hero-v2">
                <div>
                    <p class="chip">Taskflow Command Center</p>
                    <h1 class="hero-title">Appels d'offres en temps réel</h1>
                    <p class="hero-lede">Centralisez les opportunités publiques, priorisez les échéances chaudes et exportez en un clic.</p>
                    <div class="cta-row">
                        <a class="cta-primary" href="?refresh=1">🔄 Rafraîchir</a>
                        <a class="cta-secondary" href="#tableau">⬇️ Export JSON</a>
                    </div>
                </div>
                <div class="metric-stack">
                    <div class="metric-card">
                        <span>Total suivi</span>
                        <strong>{total_db}</strong>
                        <small>{filtered} visibles avec vos filtres</small>
                    </div>
                    <div class="metric-card">
                        <span>Régions représentées</span>
                        <strong>{unique_regions}</strong>
                        <small>variété territoriale</small>
                    </div>
                    <div class="metric-card">
                        <span>Procédures</span>
                        <strong>{unique_proc}</strong>
                        <small>modes de consultation</small>
                    </div>
                </div>
            </section>
            """
        ),
        unsafe_allow_html=True,
    )


def render_summary(df: pd.DataFrame, meta: Dict[str, Iterable]) -> None:
    total_displayed = len(df)
    total_db = meta.get("count", total_displayed)
    deadlines = pd.to_datetime(df.get("Date limite"), errors="coerce") if not df.empty else pd.Series(dtype="datetime64[ns]")
    now_ts = pd.Timestamp(timezone.now())
    next_deadline = deadlines.min() if not deadlines.empty else None
    closing_soon = deadlines[(deadlines >= now_ts) & (deadlines <= now_ts + pd.Timedelta(days=7))]
    unique_procedures = int(df["Procédure"].nunique()) if not df.empty else 0
    unique_regions = int(df["Région"].nunique()) if not df.empty else 0

    stats = [
        {
            "label": "Opportunités affichées",
            "value": f"{total_displayed:,}",
            "helper": f"sur {total_db:,} enregistrées",
        },
        {
            "label": "Échéances (< 7 jours)",
            "value": str(len(closing_soon)),
            "helper": "priorisez ces dossiers",
        },
        {
            "label": "Procédures couvertes",
            "value": unique_procedures,
            "helper": f"{unique_regions} régions concernées",
        },
        {
            "label": "Prochaine échéance",
            "value": _format_datetime(next_deadline) if next_deadline is not None else "—",
            "helper": "d'après vos filtres",
        },
    ]

    card_markup = [
        _html_block(
            f"""
            <div class='stat-card'>
                <p class='stat-label'>{html.escape(str(stat['label']))}</p>
                <p class='stat-value'>{html.escape(str(stat['value']))}</p>
                <p class='stat-helper'>{html.escape(str(stat['helper']))}</p>
            </div>
            """
        )
        for stat in stats
    ]
    st.markdown(
        _html_block(
            f"""
            <div class='stat-grid'>
                {''.join(card_markup)}
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def render_focus_cards(df: pd.DataFrame) -> None:
    st.caption("Fiches détaillées prêtes à partager avec votre équipe.")
    for record in df.to_dict("records"):
        deadline = _format_datetime(record.get("Date limite"))
        links = record.get("Liens")
        link_section = ""
        if isinstance(links, str):
            try:
                parsed_links = json.loads(links)
            except json.JSONDecodeError:
                parsed_links = {}
            if isinstance(parsed_links, dict) and parsed_links:
                items = "".join(
                    f"<li><a href='{html.escape(url)}' target='_blank'>{html.escape(label.title())}</a></li>"
                    for label, url in parsed_links.items()
                    if url
                )
                link_section = f"<ul>{items}</ul>"
        st.markdown(
            _html_block(
                f"""
                <div class='detail-card'>
                    <h4>{html.escape(record.get('Titre', 'Sans titre'))}</h4>
                    <p><strong>Acheteur</strong> : {html.escape(record.get('Acheteur', 'N/A'))}</p>
                    <p><strong>Localisation</strong> : {html.escape(record.get('Localisation', 'Non renseignée'))}</p>
                    <p><strong>Procédure</strong> : {html.escape(record.get('Procédure', '—'))} · <strong>Catégorie</strong> : {html.escape(record.get('Catégorie', '—'))}</p>
                    <p><strong>Échéance</strong> : {deadline}</p>
                    {link_section}
                </div>
                """
            ),
            unsafe_allow_html=True,
        )


def _ensure_board_state(df: pd.DataFrame) -> Dict[str, str]:
    """Keep session-based statuses aligned with the dataframe content."""
    status_map = st.session_state.setdefault("board_status", {})
    if df.empty:
        status_map.clear()
        return status_map
    identifiers = [str(val) for val in (df["ID"].tolist() if "ID" in df.columns else df["Titre"].tolist())]
    for identifier in identifiers:
        status_map.setdefault(identifier, BOARD_STAGES[0])
    for stale in [key for key in status_map.keys() if key not in identifiers]:
        status_map.pop(stale, None)
    return status_map


def _update_board_stage(card_id: str, widget_key: str) -> None:
    value = st.session_state.get(widget_key, BOARD_STAGES[0])
    st.session_state.setdefault("board_status", {})[card_id] = value


def render_scrap_board(df: pd.DataFrame) -> None:
    """Interactive board with Backlog → Done swimlanes."""
    status_map = _ensure_board_state(df)
    grouped: Dict[str, List[Tuple[str, Dict[str, str]]]] = {stage: [] for stage in BOARD_STAGES}
    payload: List[Dict[str, List[str]]] = []
    for record in df.to_dict("records"):
        card_id = str(record.get("ID") or record.get("Titre"))
        stage = status_map.get(card_id, BOARD_STAGES[0])
        grouped.setdefault(stage, []).append((card_id, record))
    for stage in BOARD_STAGES:
        items = []
        for card_id, record in grouped.get(stage, []):
            title = record.get("Titre", "Sans titre")
            buyer = record.get("Acheteur", "N/A")
            deadline = _format_datetime(record.get("Date limite"))
            label = f"#{card_id} · {title}\nAcheteur : {buyer}\nÉchéance : {deadline}"
            items.append(label)
        payload.append({"header": stage, "items": items})

    if HAS_SORTABLE and not df.empty:
        custom_style = """
        .sortable-component {
            display: grid;
            grid-template-columns: repeat(4, minmax(220px, 1fr));
            gap: 1rem;
            align-items: flex-start;
        }
        .sortable-container {
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            align-items: stretch;
            background: rgba(255,255,255,0.03);
            border-radius: 18px;
            border: 1px solid var(--tf-border);
            min-height: 420px;
            padding: 1rem;
        }
        .sortable-container-header {
            font-size: 0.75rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--tf-muted);
            margin-bottom: 0.6rem;
        }
        .sortable-container-body {
            display: flex;
            flex-direction: column;
            flex: 1;
            justify-content: flex-start;
            gap: 0.6rem;
        }
        .sortable-item {
            background: rgba(5, 7, 13, 0.65);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.08);
            padding: 0.9rem;
            color: var(--tf-text);
            white-space: pre-wrap;
            line-height: 1.35;
            box-shadow: 0 18px 32px rgba(5,7,13,0.45);
        }
        """
        sorted_payload = sort_items(  # type: ignore[misc]
            payload,
            direction="horizontal",
            multi_containers=True,
            custom_style=custom_style,
            key="scrap-board-sortable",
        ) or payload
        for column in sorted_payload:
            stage = column.get("header") or BOARD_STAGES[0]
            for item in column.get("items", []):
                card_id = str(item).split("·", 1)[0].replace("#", "").strip()
                status_map[card_id] = stage
        counts = {stage: sum(1 for s in status_map.values() if s == stage) for stage in BOARD_STAGES}
        st.caption(" · ".join(f"{stage}: {counts.get(stage, 0)}" for stage in BOARD_STAGES))
        return
    elif not HAS_SORTABLE:
        st.info("Installez 'streamlit-sortables' (pip install streamlit-sortables) pour activer le glisser-déposer.")

    columns = st.columns(len(BOARD_STAGES), gap="large")
    for idx, stage in enumerate(BOARD_STAGES):
        with columns[idx]:
            st.markdown(f"**{stage}** ({len(grouped.get(stage, []))})")
            if not grouped.get(stage):
                st.caption("Aucune carte")
                continue
            for card_id, record in grouped.get(stage, []):
                st.markdown(
                    _html_block(
                        f"""
                        <article class='board-card'>
                            <h4>{html.escape(record.get('Titre', 'Sans titre'))}</h4>
                            <div class='card-meta'>Acheteur : {html.escape(str(record.get('Acheteur', 'N/A')))}</div>
                            <div class='card-meta'>Échéance : {_format_datetime(record.get('Date limite'))}</div>
                        </article>
                        """
                    ),
                    unsafe_allow_html=True,
                )
                if not HAS_SORTABLE:
                    select_key = f"stage-select-{card_id}"
                    if select_key not in st.session_state:
                        st.session_state[select_key] = status_map.get(card_id, BOARD_STAGES[0])
                    st.selectbox(
                        "Changer d'étape",
                        BOARD_STAGES,
                        key=select_key,
                        label_visibility="collapsed",
                        on_change=_update_board_stage,
                        args=(card_id, select_key),
                    )


def sidebar_filters(meta: Dict[str, Iterable]) -> Tuple[Dict[str, str], str]:
    st.sidebar.header("Filtres")
    keyword = st.sidebar.text_input("Recherche plein texte", placeholder="ex: plomberie, parking...")
    category = st.sidebar.selectbox("Catégorie", options=["" ] + meta["categories"], index=0)
    procedure = st.sidebar.selectbox("Procédure", options=["" ] + meta["procedures"], index=0)
    region = st.sidebar.selectbox("Région", options=["" ] + meta["regions"], index=0)
    department = st.sidebar.selectbox("Département", options=["" ] + meta["departments"], index=0)

    min_deadline = meta.get("min_deadline")
    max_deadline = meta.get("max_deadline")
    default_range = None
    if min_deadline and max_deadline:
        default_range = (min_deadline.date(), max_deadline.date())
    date_range = st.sidebar.date_input(
        "Intervalle de dates limites",
        value=default_range,
        min_value=min_deadline.date() if min_deadline else None,
        max_value=max_deadline.date() if max_deadline else None,
    )
    start_date = end_date = None
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    ordering_label = st.sidebar.selectbox(
        "Tri",
        options={
            "Date limite la plus proche": "deadline_at",
            "Date limite la plus lointaine": "-deadline_at",
            "Derniers scrappés": "-scraped_at",
            "Plus anciens": "scraped_at",
        },
        format_func=lambda key: key,
    )
    ordering = {
        "Date limite la plus proche": "deadline_at",
        "Date limite la plus lointaine": "-deadline_at",
        "Derniers scrappés": "-scraped_at",
        "Plus anciens": "scraped_at",
    }[ordering_label]

    limit = st.sidebar.slider("Nombre maximum de lignes", min_value=50, max_value=1000, value=200, step=50)
    if st.sidebar.button("Afficher le backlog scrapping"):
        st.session_state["show_backlog_modal"] = True
    if st.session_state.get("show_backlog_modal"):
        if st.sidebar.button("Fermer le backlog", key="sidebar-close-backlog"):
            st.session_state["show_backlog_modal"] = False

    filters = {
        "keyword": keyword.strip(),
        "category": category or "",
        "procedure": procedure or "",
        "region": region or "",
        "department": department or "",
        "start_date": start_date,
        "end_date": end_date,
        "ordering": ordering,
        "limit": limit,
    }
    return filters, ordering_label


def main() -> None:
    meta = load_filter_metadata()
    filters, ordering_label = sidebar_filters(meta)

    df = build_dataframe(filters)
    render_hero(meta, df)
    render_summary(df, meta)

    st.markdown(
        f"<p class='stat-helper'>Filtre actif : <strong>{html.escape(ordering_label)}</strong> · {len(df)} appels d'offres affichés</p>",
        unsafe_allow_html=True,
    )

    if df.empty:
        st.info("Aucun résultat pour ces filtres.")
        st.session_state["show_backlog_modal"] = False
        return

    backlog_intro = _html_block(
        """
        <section class='detail-card'>
            <h2>Backlog des dossiers collectés</h2>
            <p class='stat-helper'>Vue opérée par l'équipe scrapping, prête à dispatcher côté back.</p>
        </section>
        """
    )

    if st.session_state.get("show_backlog_modal"):
        if STREAMLIT_HAS_MODAL:
            with st.modal("Backlog scrapping", key="backlog-modal"):
                st.markdown(backlog_intro, unsafe_allow_html=True)
                render_scrap_board(df)
                if st.button("Fermer le backlog", key="close-backlog"):
                    st.session_state["show_backlog_modal"] = False
        else:
            st.warning("Cette version de Streamlit ne prend pas en charge les pop-ups natives; affichage intégré ci-dessous.")
            st.markdown(backlog_intro, unsafe_allow_html=True)
            render_scrap_board(df)
            if st.button("Fermer le backlog", key="close-backlog-fallback"):
                st.session_state["show_backlog_modal"] = False
    else:
        st.caption("Cliquez sur \"Afficher le backlog scrapping\" dans la barre latérale pour piloter le board.")


def render_kanban(df: pd.DataFrame) -> None:
    """Display a lightweight Kanban grouped by a selected dimension."""
    st.caption("Organisez les marchés par file d'attente thématique.")
    if df.empty:
        st.caption("Ajoutez des appels d'offres pour alimenter le kanban.")
        return

    group_label = st.selectbox("Grouper les colonnes par", list(KANBAN_DIMENSIONS.keys()))
    field = KANBAN_DIMENSIONS[group_label]
    max_cards = st.slider("Cartes max par colonne", 3, 15, 6)
    st.markdown(f"<p class='stat-helper'>Regroupement actif : <span class='chip'>{html.escape(group_label)}</span></p>", unsafe_allow_html=True)

    grouped = df.groupby(field)
    ordered_keys = sorted(grouped.groups.keys(), key=lambda value: str(value or ""))
    columns_html = []
    for key in ordered_keys:
        subset = grouped.get_group(key)
        cards = []
        for _, row in subset.head(max_cards).iterrows():
            cards.append(
                _html_block(
                    f"""
                    <article class='board-card'>
                        <h4>{html.escape(row['Titre'])}</h4>
                        <div class='card-meta'>Limite : {_format_datetime(row['Date limite'])}</div>
                        <div class='card-meta'>Acheteur : {html.escape(str(row['Acheteur']))}</div>
                        <div>
                            <span class='chip chip-inline'>{html.escape(str(row['Procédure'] or 'Procédure ?'))}</span>
                            <span class='chip chip-inline'>{html.escape(str(row['Région'] or 'Région ?'))}</span>
                        </div>
                    </article>
                    """
                )
            )
        column_html = _html_block(
            f"""
            <section class='board-column'>
                <h3>{html.escape(str(key or 'Non renseigné'))} · {len(subset)}</h3>
                {''.join(cards) or "<div class='card-meta'>Aucune carte</div>"}
            </section>
            """
        )
        columns_html.append(column_html)
    st.markdown(
        _html_block(
            f"""
            <div class='board-columns'>
                {''.join(columns_html)}
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def chunked(seq: Sequence, size: int) -> Iterator[List]:
    seq_iter = iter(seq)
    while True:
        block = list(islice(seq_iter, size))
        if not block:
            break
        yield block


if __name__ == "__main__":
    main()
