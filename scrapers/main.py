import logging
from os.path import join

from hdx.location.adminlevel import AdminLevel
from hdx.location.country import Country
from hdx.scraper.runner import Runner
from hdx.scraper.utilities.fallbacks import Fallbacks
from hdx.scraper.utilities.region_lookup import RegionLookup
from hdx.scraper.utilities.sources import Sources
from hdx.scraper.utilities.writer import Writer

from .fts import FTS
from .inform import Inform
from .iom_dtm import IOMDTM
from .ipc import IPC
from .unhcr import UNHCR
from .whowhatwhere import WhoWhatWhere

logger = logging.getLogger(__name__)


def get_indicators(
    configuration,
    today,
    outputs,
    tabs,
    scrapers_to_run=None,
    countries_override=None,
    errors_on_exit=None,
    use_live=True,
    fallbacks_root="",
):
    Country.countriesdata(
        use_live=use_live,
        country_name_overrides=configuration["country_name_overrides"],
        country_name_mappings=configuration["country_name_mappings"],
    )

    if countries_override:
        countries = countries_override
    else:
        countries = configuration["countries"]
    hrp_countries = configuration["HRPs"]
    configuration["countries_fuzzy_try"] = countries
    adminlevel = AdminLevel(configuration)
    adminlevel.setup_from_admin_info(configuration["admin_info"])
    regional_configuration = configuration["regional"]
    RegionLookup.load(regional_configuration, countries, {"HRPs": hrp_countries})
    if fallbacks_root is not None:
        fallbacks_path = join(fallbacks_root, configuration["json"]["output"])
        levels_mapping = {
            "global": "allregions_data",
            "regional": "regional_data",
            "national": "national_data",
            "subnational": "subnational_data",
        }
        Fallbacks.add(
            fallbacks_path,
            levels_mapping=levels_mapping,
            sources_key="sources_data",
        )
    Sources.set_default_source_date_format("%Y-%m-%d")
    runner = Runner(
        countries,
        today,
        errors_on_exit=errors_on_exit,
        scrapers_to_run=scrapers_to_run,
    )
    configurable_scrapers = dict()
    for level_name in "national", "subnational", "allregions":
        if level_name == "allregions":
            level = "single"
        else:
            level = level_name
        suffix = f"_{level_name}"
        configurable_scrapers[level_name] = runner.add_configurables(
            configuration[f"scraper{suffix}"],
            level,
            adminlevel=adminlevel,
            level_name=level_name,
            suffix=suffix,
        )
    ipc = IPC(configuration["ipc"], today, countries, adminlevel)

    fts = FTS(configuration["fts"], today, outputs, countries)
    unhcr = UNHCR(configuration["unhcr"], today, countries)
    inform = Inform(configuration["inform"], today, countries)
    national_names = configurable_scrapers["national"] + [
        "fts",
        "unhcr",
        "inform",
        "ipc",
    ]

    whowhatwhere = WhoWhatWhere(configuration["whowhatwhere"], today, adminlevel)
    iomdtm = IOMDTM(configuration["iom_dtm"], today, adminlevel)

    subnational_names = configurable_scrapers["subnational"] + [
        "whowhatwhere",
        "iom_dtm",
    ]
    subnational_names.insert(1, "ipc")

    runner.add_customs(
        (
            ipc,
            fts,
            unhcr,
            inform,
            whowhatwhere,
            iomdtm,
        )
    )

    regional_names = runner.add_aggregators(
        True,
        regional_configuration["aggregate"],
        "national",
        "regional",
        RegionLookup.iso3_to_regions["ALL"],
        force_add_to_run=True,
    )

    runner.run(
        prioritise_scrapers=(
            "population_national",
            "population_subnational",
            "population_allregions",
        )
    )

    writer = Writer(runner, outputs)
    if "national" in tabs:
        flag_countries = {
            "header": "ishrp",
            "hxltag": "#meta+ishrp",
            "countries": hrp_countries,
        }
        writer.update_national(
            countries,
            names=national_names,
            flag_countries=flag_countries,
            iso3_to_region=RegionLookup.iso3_to_regions["ALL"],
            ignore_regions=("ALL",),
        )
    regional_rows = writer.get_regional_rows(
        RegionLookup.regions,
        names=regional_names,
    )
    if "regional" in tabs:
        writer.update_regional(
            regional_rows,
        )
    if "allregions" in tabs:
        allregions_names = configurable_scrapers["allregions"]
        allregions_rows = writer.get_toplevel_rows(names=allregions_names)
        writer.update_toplevel(
            allregions_rows,
            regional_rows=regional_rows,
            regional_first=True,
        )
    if "subnational" in tabs:
        writer.update_subnational(adminlevel, names=subnational_names)

    adminlevel.output_matches()
    adminlevel.output_ignored()
    adminlevel.output_errors()

    if "sources" in tabs:
        writer.update_sources(
            additional_sources=configuration["additional_sources"],
        )
    return countries
