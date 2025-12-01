"""Streamlit dashboard that reads tender data directly from the Django ORM."""
from __future__ import annotations

import json
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

from tenders.models import Tender  # noqa: E402

st.set_page_config(page_title="Tenders dashboard", layout="wide")


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
    st.title("Appels d'offres (Streamlit)")
    st.caption("Visualisation rapide des données scrapées et stockées dans Django")

    filters, ordering_label = sidebar_filters(meta)

    df = build_dataframe(filters)
    st.write(
        f"{len(df)} appels d'offres affichés sur {meta['count']} en base • Tri: {ordering_label}"
    )

    if df.empty:
        st.info("Aucun résultat pour ces filtres.")
        return

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
    )

    st.subheader("Focus par appel d'offre")
    for _, row in df.iterrows():
        with st.expander(row["Titre"]):
            st.write(
                "**Acheteur**:", row["Acheteur"], " | **Procédure**:", row["Procédure"], " | **Catégorie**:", row["Catégorie"]
            )
            st.write("**Localisation**:", row["Localisation"], " | **Région**:", row["Région"], " | **Département**:", row["Département"])
            st.write("**Date limite**:", row["Date limite"])
            try:
                links = json.loads(row["Liens"])
                for label, url in links.items():
                    st.markdown(f"- [{label}]({url})")
            except json.JSONDecodeError:
                st.write(row["Liens"])

    render_kanban(df)


def render_kanban(df: pd.DataFrame) -> None:
    """Display a lightweight Kanban grouped by a selected dimension."""
    st.subheader("Vue Kanban (lecture seule)")
    if df.empty:
        st.caption("Ajoutez des appels d'offres pour alimenter le kanban.")
        return

    group_label = st.selectbox("Grouper les colonnes par", list(KANBAN_DIMENSIONS.keys()))
    field = KANBAN_DIMENSIONS[group_label]
    max_cards = st.slider("Cartes max par colonne", 3, 15, 6)

    grouped = df.groupby(field)
    ordered_keys = sorted(grouped.groups.keys(), key=lambda value: str(value or ""))

    for chunk in chunked(ordered_keys, 4):
        cols = st.columns(len(chunk))
        for col, key in zip(cols, chunk):
            subset = grouped.get_group(key)
            col.markdown(f"**{key or 'Non renseigné'}** ({len(subset)})")
            for _, row in subset.head(max_cards).iterrows():
                col.markdown(
                    f"<div style='border:1px solid #d9d9d9;padding:8px;border-radius:6px;margin-bottom:6px;'>"
                    f"<strong>{row['Titre']}</strong><br/>"
                    f"<small>Limite: {row['Date limite']}<br/>Procédure: {row['Procédure']}</small>"
                    "</div>",
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
