import logging

from hdx.location.adminone import AdminOne
from hdx.location.country import Country
from hdx.scraper.runner import Runner

from .covax_deliveries import CovaxDeliveries
from .education_closures import EducationClosures
from .education_enrolment import EducationEnrolment
from .food_prices import FoodPrices
from .fts import FTS
from .inform import Inform
from .iom_dtm import IOMDTM
from .ipc_old import IPC
from .unhcr import UNHCR
from .utilities.update_tabs import (
    update_national,
    update_regional,
    update_sources,
    update_subnational,
)
from .vaccination_campaigns import VaccinationCampaigns
from .who_covid import WHOCovid
from .whowhatwhere import WhoWhatWhere

logger = logging.getLogger(__name__)


def get_indicators(
    configuration,
    today,
    retriever,
    outputs,
    tabs,
    scrapers_to_run=None,
    basic_auths=dict(),
    other_auths=dict(),
    countries_override=None,
    errors_on_exit=None,
    use_live=True,
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
    configuration["countries_fuzzy_try"] = countries
    downloader = retriever.downloader
    adminone = AdminOne(configuration)
    runner = Runner(
        countries,
        adminone,
        downloader,
        basic_auths,
        today,
        errors_on_exit=errors_on_exit,
        scrapers_to_run=scrapers_to_run,
    )
    configurable_scrapers = dict()
    for level_name in "national", "subnational", "regional":
        if level_name == "regional":
            level = "single"
        else:
            level = level_name
        suffix = f"_{level_name}"
        configurable_scrapers[level_name] = runner.add_configurables(
            configuration[f"scraper{suffix}"], level, level_name, suffix=suffix
        )
    who_covid = WHOCovid(
        configuration["who_covid"],
        today,
        outputs,
        countries,
    )
    ipc = IPC(configuration["ipc"], today, countries, adminone, downloader)

    fts = FTS(configuration["fts"], today, outputs, countries, basic_auths)
    food_prices = FoodPrices(
        configuration["food_prices"], today, countries, retriever, basic_auths
    )
    vaccination_campaigns = VaccinationCampaigns(
        configuration["vaccination_campaigns"],
        today,
        countries,
        downloader,
        outputs,
    )
    unhcr = UNHCR(configuration["unhcr"], today, countries, downloader)
    inform = Inform(configuration["inform"], today, countries, other_auths)
    covax_deliveries = CovaxDeliveries(
        configuration["covax_deliveries"], today, countries, downloader
    )
    education_closures = EducationClosures(
        configuration["education_closures"],
        today,
        countries,
        downloader,
    )
    education_enrolment = EducationEnrolment(
        configuration["education_enrolment"],
        education_closures,
        countries,
        downloader,
    )
    national_names = configurable_scrapers["national"] + [
        "food_prices",
        "vaccination_campaigns",
        "fts",
        "unhcr",
        "inform",
        "ipc",
        "covax_deliveries",
        "education_closures",
        "education_enrolment",
    ]
    national_names.insert(1, "who_covid")

    whowhatwhere = WhoWhatWhere(
        configuration["whowhatwhere"], today, adminone, downloader
    )
    iomdtm = IOMDTM(configuration["iom_dtm"], today, adminone, downloader)
    regional_names = ["who_covid", "fts"] + configurable_scrapers["regional"]

    subnational_names = configurable_scrapers["subnational"] + [
        "whowhatwhere",
        "iom_dtm",
    ]
    subnational_names.insert(1, "ipc")

    runner.add_customs(
        (
            who_covid,
            ipc,
            fts,
            food_prices,
            vaccination_campaigns,
            unhcr,
            inform,
            covax_deliveries,
            education_closures,
            education_enrolment,
            whowhatwhere,
            iomdtm,
        )
    )
    runner.run(
        prioritise_scrapers=(
            "population_national",
            "population_subnational",
            "population_regional",
        )
    )

    if "regional" in tabs:
        update_regional(runner, regional_names, outputs)
    if "national" in tabs:
        update_national(
            runner,
            national_names,
            countries,
            outputs,
        )
    if "subnational" in tabs:
        update_subnational(runner, subnational_names, adminone, outputs)

    adminone.output_matches()
    adminone.output_ignored()
    adminone.output_errors()

    if "sources" in tabs:
        update_sources(runner, configuration, outputs)
    return countries
