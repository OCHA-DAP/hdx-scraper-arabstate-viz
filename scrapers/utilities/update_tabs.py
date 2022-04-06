import logging

from hdx.location.country import Country

logger = logging.getLogger(__name__)

regions_headers = (("regionnames",), ("#region+name",))
national_headers = (
    ("iso3", "countryname"),
    ("#country+code", "#country+name"),
)
subnational_headers = (
    ("iso3", "countryname", "adm1_pcode", "adm1_name"),
    ("#country+code", "#country+name", "#adm1+code", "#adm1+name"),
)
sources_headers = (
    ("Indicator", "Date", "Source", "Url"),
    ("#indicator+name", "#date", "#meta+source", "#meta+url"),
)


def update_tab(outputs, name, data):
    if not data:
        return
    logger.info(f"Updating tab: {name}")
    for output in outputs.values():
        output.update_tab(name, data)


def get_allregions_rows(runner, names, overrides=dict()):
    return runner.get_rows("allregions", ("value",), names=names, overrides=overrides)


def get_regional_rows(runner, names, regional):
    return runner.get_rows(
        "regional", regional, regional_headers, (lambda adm: adm,), names=names
    )


def update_allregions(outputs, allregions_rows, regions_rows=tuple()):
    if not allregions_rows:
        return
    if regions_rows:
        adm_header = regions_rows[1].index("#region+name")
        rows_to_insert = (list(), list(), list())
        for row in regions_rows[2:]:
            if row[adm_header] == "ALL":
                for i, hxltag in enumerate(regions_rows[1]):
                    if hxltag == "#region+name":
                        continue
                    rows_to_insert[0].append(regions_rows[0][i])
                    rows_to_insert[1].append(hxltag)
                    rows_to_insert[2].append(row[i])
        allregions_rows[0] = rows_to_insert[0] + allregions_rows[0]
        allregions_rows[1] = rows_to_insert[1] + allregions_rows[1]
        allregions_rows[2] = rows_to_insert[2] + allregions_rows[2]
    update_tab(outputs, "allregions", allregions_rows)


def update_regional(
    outputs, regional_rows, allregions_rows=tuple(), additional_allregions_headers=tuple()
):
    if not regional_rows:
        return
    allregions_values = dict()
    if allregions_rows:
        for i, header in enumerate(allregions_rows[0]):
            if header in additional_allregions_headers:
                allregions_values[header] = allregions_rows[2][i]
    adm_header = regional_rows[1].index("#region+name")
    for row in regional_rows[2:]:
        if row[adm_header] == "allregions":
            for i, header in enumerate(regional_rows[0]):
                value = allregions_values.get(header)
                if value is None:
                    continue
                row[i] = value
    update_tab(outputs, "regional", regional_rows)


def update_national(runner, names, countries, outputs):
    name_fn = lambda adm: Country.get_country_name_from_iso3(adm)

    fns = (lambda adm: adm, name_fn)
    rows = runner.get_rows("national", countries, national_headers, fns, names=names)
    update_tab(outputs, "national", rows)


def update_subnational(runner, names, adminone, outputs):
    def get_country_name(adm):
        countryiso3 = adminone.pcode_to_iso3[adm]
        return Country.get_country_name_from_iso3(countryiso3)

    fns = (
        lambda adm: adminone.pcode_to_iso3[adm],
        get_country_name,
        lambda adm: adm,
        lambda adm: adminone.pcode_to_name[adm],
    )
    rows = runner.get_rows(
        "subnational", adminone.pcodes, subnational_headers, fns, names=names
    )
    update_tab(outputs, "subnational", rows)


def update_sources(runner, configuration, outputs):
    sources = runner.get_sources(additional_sources=configuration["additional_sources"])
    update_tab(outputs, "sources", list(sources_headers) + sources)
