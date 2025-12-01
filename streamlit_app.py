"""Streamlit dashboard that reads tender data directly from the Django ORM."""
from __future__ import annotations

import json
import html
import os
import sys
from datetime import date, datetime, time
from itertools import islice
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Sequence, Tuple

import pandas as pd
import streamlit as st

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
AUTO_BOOTSTRAP_ENABLED = os.getenv("TASKFLOW_AUTO_BOOTSTRAP", "1").lower() not in {"0", "false", "no", "off"}
try:
    BOOTSTRAP_PAGES = max(1, int(os.getenv("TASKFLOW_BOOTSTRAP_PAGES", "1")))
except ValueError:
    BOOTSTRAP_PAGES = 1

THEME_CSS = """
<style>
:root {
    --tf-bg: #f4f5f7;
    --tf-surface: #ffffff;
    --tf-border: #dfe1e6;
    --tf-text: #172b4d;
    --tf-muted: #6b778c;
    --tf-primary: #0052cc;
}

body {
    background: var(--tf-bg);
    color: var(--tf-text);
    font-family: "Helvetica Neue", Inter, -apple-system, BlinkMacSystemFont, sans-serif;
}

[data-testid="stSidebar"] {
    background: var(--tf-surface);
    border-right: 1px solid var(--tf-border);
}

.board-toolbar {
    background: var(--tf-surface);
    border: 1px solid var(--tf-border);
    border-radius: 8px;
    padding: 0.8rem 1rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1rem;
}

.toolbar-left h1 {
    font-size: 1.3rem;
    margin: 0;
}

.toolbar-meta {
    color: var(--tf-muted);
    font-size: 0.9rem;
}

.chip {
    background: #ebecf0;
    border-radius: 999px;
    padding: 0.25rem 0.8rem;
    font-size: 0.85rem;
    color: var(--tf-text);
}

.stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.75rem;
    margin-bottom: 0.5rem;
}

.stat-card {
    background: var(--tf-surface);
    border-radius: 8px;
    border: 1px solid var(--tf-border);
    padding: 0.9rem;
}

.stat-label {
    color: var(--tf-muted);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.stat-value {
    font-size: 1.4rem;
    font-weight: 600;
    margin: 0.15rem 0;
}

.board-columns {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
}

.board-column {
    background: #ebecf0;
    border-radius: 8px;
    padding: 0.5rem;
    min-height: 200px;
}

.board-column h3 {
    font-size: 0.85rem;
    text-transform: uppercase;
    color: var(--tf-muted);
    margin: 0 0 0.5rem;
    letter-spacing: 0.08em;
}

.board-card {
    background: var(--tf-surface);
    border-radius: 6px;
    border: 1px solid var(--tf-border);
    padding: 0.75rem;
    margin-bottom: 0.5rem;
    box-shadow: 0 1px 1px rgba(9, 30, 66, 0.25);
}

.board-card h4 {
    font-size: 0.95rem;
    margin: 0 0 0.3rem;
}

.card-meta {
    font-size: 0.8rem;
    color: var(--tf-muted);
}

.detail-card {
    border: 1px solid var(--tf-border);
    border-radius: 8px;
    padding: 1rem;
    background: var(--tf-surface);
    margin-bottom: 0.8rem;
}

.detail-card h4 {
    margin: 0 0 0.4rem;
}

.stat-helper {
    color: var(--tf-muted);
}
</style>
"""

st.markdown(THEME_CSS, unsafe_allow_html=True)


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


def render_board_toolbar(meta: Dict[str, Iterable]) -> None:
    total = meta.get("count", 0)
    st.markdown(
        f"""
        <section class="board-toolbar">
            <div class="toolbar-left">
                <h1>Kanban appels d'offres</h1>
                <p class="toolbar-meta">{total} appels d'offres suivis dans Taskflow</p>
            </div>
            <div class="chip">Vue type Jira</div>
        </section>
        """,
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

    cards = "".join(
        f"""
        <div class='stat-card'>
            <p class='stat-label'>{html.escape(str(stat['label']))}</p>
            <p class='stat-value'>{html.escape(str(stat['value']))}</p>
            <p class='stat-helper'>{html.escape(str(stat['helper']))}</p>
        </div>
        """
        for stat in stats
    )
    st.markdown(f"<div class='stat-grid'>{cards}</div>", unsafe_allow_html=True)


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
            f"""
            <div class='detail-card'>
                <h4>{html.escape(record.get('Titre', 'Sans titre'))}</h4>
                <p><strong>Acheteur</strong> : {html.escape(record.get('Acheteur', 'N/A'))}</p>
                <p><strong>Localisation</strong> : {html.escape(record.get('Localisation', 'Non renseignée'))}</p>
                <p><strong>Procédure</strong> : {html.escape(record.get('Procédure', '—'))} · <strong>Catégorie</strong> : {html.escape(record.get('Catégorie', '—'))}</p>
                <p><strong>Échéance</strong> : {deadline}</p>
                {link_section}
            </div>
            """,
            unsafe_allow_html=True,
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
    render_board_toolbar(meta)

    filters, ordering_label = sidebar_filters(meta)

    df = build_dataframe(filters)
    render_summary(df, meta)

    st.markdown(
        f"<p class='stat-helper'>Filtre actif : <strong>{html.escape(ordering_label)}</strong> · {len(df)} appels d'offres affichés</p>",
        unsafe_allow_html=True,
    )

    if df.empty:
        st.info("Aucun résultat pour ces filtres.")
        return

    tab_tableau, tab_kanban, tab_fiches = st.tabs([
        "Tableau interactif",
        "Vue Kanban",
        "Cartes détaillées",
    ])

    with tab_tableau:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={"Liens": st.column_config.TextColumn("Liens JSON")},
        )
        json_payload = df.to_json(orient="records", force_ascii=False, indent=2)
        st.download_button(
            label="Télécharger le JSON",
            data=json_payload,
            file_name="tenders_streamlit.json",
            mime="application/json",
            use_container_width=True,
        )

    with tab_kanban:
        render_kanban(df)

    with tab_fiches:
        render_focus_cards(df)


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
                f"""
                <article class='board-card'>
                    <h4>{html.escape(row['Titre'])}</h4>
                    <div class='card-meta'>Limite : {_format_datetime(row['Date limite'])}</div>
                    <div class='card-meta'>Acheteur : {html.escape(str(row['Acheteur']))}</div>
                </article>
                """
            )
        column_html = f"""
        <section class='board-column'>
            <h3>{html.escape(str(key or 'Non renseigné'))} · {len(subset)}</h3>
            {''.join(cards) or "<div class='card-meta'>Aucune carte</div>"}
        </section>
        """
        columns_html.append(column_html)
    st.markdown(f"<div class='board-columns'>{''.join(columns_html)}</div>", unsafe_allow_html=True)


def chunked(seq: Sequence, size: int) -> Iterator[List]:
    seq_iter = iter(seq)
    while True:
        block = list(islice(seq_iter, size))
        if not block:
            break
        yield block


if __name__ == "__main__":
    main()
