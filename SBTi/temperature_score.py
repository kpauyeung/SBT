import itertools
from enum import Enum
from typing import Optional, Tuple, Type, Dict, List

import pandas as pd
import numpy as np

from .interfaces import ScenarioInterface
from .portfolio_aggregation import PortfolioAggregation, PortfolioAggregationMethod
from .configs import TemperatureScoreConfig


class ScenarioType(Enum):
    """
    A scenario defines which scenario should be run.
    """
    TARGETS = 1
    APPROVED_TARGETS = 2
    HIGHEST_CONTRIBUTORS = 3
    HIGHEST_CONTRIBUTORS_APPROVED = 4

    @staticmethod
    def from_int(value) -> Optional['ScenarioType']:
        value_map = {
            1: ScenarioType.TARGETS,
            2: ScenarioType.APPROVED_TARGETS,
            3: ScenarioType.HIGHEST_CONTRIBUTORS,
            4: ScenarioType.HIGHEST_CONTRIBUTORS_APPROVED
        }
        return value_map.get(value, None)


class EngagementType(Enum):
    """
    An engagement type defines how the companies will be engaged.
    """

    SET_TARGETS = 1
    SET_SBTI_TARGETS = 2

    @staticmethod
    def from_int(value) -> 'EngagementType':
        """
        Convert an integer to an engagement type.

        :param value: The value to convert
        :return:
        """
        value_map = {
            0: EngagementType.SET_TARGETS,
            1: EngagementType.SET_SBTI_TARGETS,
        }
        return value_map.get(value, EngagementType.SET_TARGETS)

    @staticmethod
    def from_string(value: str) -> 'EngagementType':
        """
        Convert a string to an engagement type.

        :param value: The value to convert
        :return:
        """
        if value is None:
            return EngagementType.SET_TARGETS

        value_map = {
            'SET_TARGETS': EngagementType.SET_TARGETS,
            'SET_SBTI_TARGETS': EngagementType.SET_SBTI_TARGETS,
        }
        return value_map.get(value.upper(), EngagementType.SET_TARGETS)


class Scenario:
    """
    A scenario defines the action the portfolio holder will take to improve its temperature score.
    """
    scenario_type: ScenarioType
    engagement_type: EngagementType

    def get_score_cap(self) -> float:
        if self.engagement_type == EngagementType.SET_TARGETS:
            return 2.0
        elif self.scenario_type == ScenarioType.APPROVED_TARGETS or \
                self.engagement_type == EngagementType.SET_SBTI_TARGETS:
            return 1.75
        else:
            return np.NaN

    def get_fallback_score(self, fallback_score: float) -> float:
        if self.scenario_type == ScenarioType.TARGETS:
            return 2.0
        else:
            return fallback_score

    @staticmethod
    def from_dict(scenario_values: dict) -> Optional['Scenario']:
        """
        Convert a dictionary to a scenario. The dictionary should have the following keys:

        * number: The scenario type as an integer
        * engagement_type: The engagement type as a string

        :param scenario_values: The dictionary to convert
        :return: A scenario object matching the input values or None, if no scenario could be matched
        """
        scenario = Scenario()
        scenario.scenario_type = ScenarioType.from_int(scenario_values.get("number", -1))
        scenario.engagement_type = EngagementType.from_string(scenario_values.get("engagement_type", ""))

        if scenario.scenario_type is not None:
            return scenario
        else:
            return None

    @staticmethod
    def from_interface(scenario_values: Optional[ScenarioInterface]) -> Optional['Scenario']:
        """
        Convert a scenario interface to a scenario.

        :param scenario_values: The interface model instance to convert
        :return: A scenario object matching the input values or None, if no scenario could be matched
        """
        if scenario_values is None:
            return None

        scenario = Scenario()
        scenario.scenario_type = ScenarioType.from_int(scenario_values.number)
        scenario.engagement_type = EngagementType.from_string(scenario_values.engagement_type)

        if scenario.scenario_type is not None:
            return scenario
        else:
            return None


class TemperatureScore(PortfolioAggregation):
    """
    This class is provides a temperature score based on the climate goals.

    :param fallback_score: The temp score if a company is not found
    :param model: The regression model to use
    :param config: A class defining the constants that are used throughout this class. This parameter is only required
                    if you'd like to overwrite a constant. This can be done by extending the TemperatureScoreConfig
                    class and overwriting one of the parameters.
    """

    def __init__(self, fallback_score: float = 3.2, model: int = 4, scenario: Optional[Scenario] = None,
                 aggregation_method: PortfolioAggregationMethod = PortfolioAggregationMethod.WATS,
                 grouping: Optional[List] = None, config: Type[TemperatureScoreConfig] = TemperatureScoreConfig):
        super().__init__(config)
        self.model = model
        self.c: Type[TemperatureScoreConfig] = config
        self.scenario: Optional[Scenario] = scenario
        self.fallback_score = fallback_score

        if self.scenario is not None:
            self.fallback_score = self.scenario.get_fallback_score(self.fallback_score)

        self.aggregation_method: PortfolioAggregationMethod = aggregation_method
        self.grouping: list = []
        if grouping is not None:
            self.grouping = grouping

        # Load the mappings from industry to SR15 goal
        self.mapping = pd.read_excel(self.c.FILE_SR15_MAPPING, header=0)
        self.regression_model = pd.read_excel(self.c.FILE_REGRESSION_MODEL_SUMMARY, header=0)
        self.regression_model = self.regression_model[self.regression_model[self.c.COLS.MODEL] == self.model]

    def get_target_mapping(self, target: pd.Series) -> Optional[str]:
        """
        Map the target onto an SR15 target (None if not available).

        :param target: The target as a row of a dataframe
        :return: The mapped SR15 target
        """
        # TODO: Use constants
        intensity_mappings = {
            "Revenue": "INT.emKyoto_gdp",
            "Product": "INT.emKyoto_gdp",
            "Cement": "INT.emKyoto_gdp",
            "Oil": "INT.emCO2EI_PE",
            "Steel": "INT.emKyoto_gdp",
            "Aluminum": "INT.emKyoto_gdp",
            "Power": "INT.emCO2EI_elecGen"
        }

        if target[self.c.COLS.TARGET_REFERENCE_NUMBER].strip().startswith(self.c.VALUE_TARGET_REFERENCE_INTENSITY_BASE):
            return intensity_mappings.get(target[self.c.COLS.INTENSITY_METRIC], None)
        else:
            return "Emissions|Kyoto Gases"

    def get_annual_reduction_rate(self, target: pd.Series) -> Optional[float]:
        """
        Get the annual reduction rate (or None if not available).

        :param target: The target as a row of a dataframe
        :return: The annual reduction
        """
        if pd.isnull(target[self.c.COLS.REDUCTION_AMBITION]):
            return None

        try:
            return target[self.c.COLS.REDUCTION_AMBITION] / float(target[self.c.COLS.END_YEAR] -
                                                                  target[self.c.COLS.START_YEAR])
        except ZeroDivisionError:
            raise ValueError("Couldn't calculate the annual reduction rate because the start and target year are the "
                             "same")

    def get_regression(self, target: pd.Series) -> Tuple[Optional[float], Optional[float]]:
        """
        Get the regression parameter and intercept from the model's output.

        :param target: The target as a row of a dataframe
        :return: The regression parameter and intercept
        """
        if pd.isnull(target[self.c.COLS.SR15]):
            return None, None

        regression = self.regression_model[
            (self.regression_model[self.c.COLS.VARIABLE] == target[self.c.COLS.SR15]) &
            (self.regression_model[self.c.COLS.SLOPE] == self.c.SLOPE_MAP[target[self.c.COLS.TIME_FRAME]])]
        if len(regression) == 0:
            return None, None
        elif len(regression) > 1:
            # There should never be more than one potential mapping
            raise ValueError("There is more than one potential regression parameter for this SR15 goal.")
        else:
            return regression.iloc[0][self.c.COLS.PARAM], regression.iloc[0][self.c.COLS.INTERCEPT]

    def _merge_regression(self, data: pd.DataFrame):
        """
        Merge the data with the regression parameters from the SBTi model.

        :param data: The data to merge
        :return: The data set, amended with the regression parameters
        """
        data[self.c.COLS.SLOPE] = data.apply(
            lambda row: self.c.SLOPE_MAP.get(row[self.c.COLS.TIME_FRAME], None),
            axis=1)
        return pd.merge(left=data, right=self.regression_model,
                        left_on=[self.c.COLS.SLOPE, self.c.COLS.SR15],
                        right_on=[self.c.COLS.SLOPE, self.c.COLS.VARIABLE],
                        how="left")

    def get_score(self, target: pd.Series) -> Tuple[float, float]:
        """
        Get the temperature score for a certain target based on the annual reduction rate and the regression parameters.

        :param target: The target as a row of a data frame
        :return: The temperature score
        """
        if pd.isnull(target[self.c.COLS.REGRESSION_PARAM]) or pd.isnull(target[self.c.COLS.REGRESSION_INTERCEPT]) \
                or pd.isnull(target[self.c.COLS.ANNUAL_REDUCTION_RATE]):
            return self.fallback_score, 1
        return max(target[self.c.COLS.REGRESSION_PARAM] * target[self.c.COLS.ANNUAL_REDUCTION_RATE] * 100 + target[
            self.c.COLS.REGRESSION_INTERCEPT], 0), 0

    def get_ghc_temperature_score(self, row: pd.Series, company_data: pd.DataFrame) -> Tuple[float, float]:
        """
        Get the aggregated temperature score and a temperature result, which indicates how much of the score is based on the default score for a certain company based on the emissions of company.

        :param company_data: The original data, grouped by company, time frame and scope category
        :param row: The row to calculate the temperature score for (if the scope of the row isn't s1s2s3, it will return the original score
        :return: The aggregated temperature score for a company
        """
        if row[self.c.COLS.SCOPE_CATEGORY] != self.c.VALUE_SCOPE_CATEGORY_S1S2S3:
            return row[self.c.COLS.TEMPERATURE_SCORE], row[self.c.TEMPERATURE_RESULTS]
        s1s2 = company_data.loc[(row[self.c.COLS.COMPANY_ID], row[self.c.COLS.TIME_FRAME],
                                 self.c.VALUE_SCOPE_CATEGORY_S1S2)]
        s3 = company_data.loc[(row[self.c.COLS.COMPANY_ID], row[self.c.COLS.TIME_FRAME],
                               self.c.VALUE_SCOPE_CATEGORY_S3)]

        try:
            # If the s3 emissions are less than 40 percent, we'll ignore them altogether, if not, we'll weigh them
            if s3[self.c.COLS.GHG_SCOPE3] / (s1s2[self.c.COLS.GHG_SCOPE12] + s3[self.c.COLS.GHG_SCOPE3]) < 0.4:
                return s1s2[self.c.COLS.TEMPERATURE_SCORE], s1s2[self.c.TEMPERATURE_RESULTS]
            else:
                company_emissions = s1s2[self.c.COLS.GHG_SCOPE12] + s3[self.c.COLS.GHG_SCOPE3]
                return ((s1s2[self.c.COLS.TEMPERATURE_SCORE] * s1s2[self.c.COLS.GHG_SCOPE12] +
                         s3[self.c.COLS.TEMPERATURE_SCORE] * s3[self.c.COLS.GHG_SCOPE3]) / company_emissions,
                        (s1s2[self.c.TEMPERATURE_RESULTS] * s1s2[self.c.COLS.GHG_SCOPE12] +
                         s3[self.c.TEMPERATURE_RESULTS] * s3[self.c.COLS.GHG_SCOPE3]) / company_emissions)

        except ZeroDivisionError:
            raise ValueError("The mean of the S1+S2 plus the S3 emissions is zero")

    def get_default_score(self, target: pd.Series) -> int:
        """
        Get the temperature score for a certain target based on the annual reduction rate and the regression parameters.

        :param target: The target as a row of a dataframe
        :return: The temperature score
        """
        if pd.isnull(target[self.c.COLS.REGRESSION_PARAM]) or pd.isnull(target[self.c.COLS.REGRESSION_INTERCEPT]) \
                or pd.isnull(target[self.c.COLS.ANNUAL_REDUCTION_RATE]):
            return 1
        return 0

    def _prepare_data(self, data: pd.DataFrame):
        """
        Prepare the data such that it can be used to calculate the temperature score.

        :param data: The original data set as a pandas data frame
        :return: The extended data frame
        """
        data[self.c.COLS.TARGET_REFERENCE_NUMBER] = data[self.c.COLS.TARGET_REFERENCE_NUMBER].replace(
            {np.nan: self.c.VALUE_TARGET_REFERENCE_ABSOLUTE}
        )
        data[self.c.COLS.SR15] = data.apply(lambda row: self.get_target_mapping(row), axis=1)
        data[self.c.COLS.ANNUAL_REDUCTION_RATE] = data.apply(lambda row: self.get_annual_reduction_rate(row), axis=1)
        data = self._merge_regression(data)
        # TODO: Move temperature result to cols
        data[self.c.COLS.TEMPERATURE_SCORE], data[self.c.TEMPERATURE_RESULTS] = zip(*data.apply(
            lambda row: self.get_score(row), axis=1))

        data = self.cap_scores(data)
        return data

    def _calculate_company_score(self, data):
        """
        Calculate the combined s1s2s3 scores for all companies.

        :param data: The original data set as a pandas data frame
        :return: The data frame, with an updated s1s2s3 temperature score
        """
        # Calculate the GHC
        company_data = data[
            [self.c.COLS.COMPANY_ID, self.c.COLS.TIME_FRAME, self.c.COLS.SCOPE_CATEGORY, self.c.COLS.GHG_SCOPE12,
             self.c.COLS.GHG_SCOPE3, self.c.COLS.TEMPERATURE_SCORE, self.c.TEMPERATURE_RESULTS]
        ].groupby([self.c.COLS.COMPANY_ID, self.c.COLS.TIME_FRAME, self.c.COLS.SCOPE_CATEGORY]).mean()

        data[self.c.COLS.TEMPERATURE_SCORE], data[self.c.TEMPERATURE_RESULTS] = zip(*data.apply(
            lambda row: self.get_ghc_temperature_score(row, company_data), axis=1
        ))
        return data

    def calculate(self, data: pd.DataFrame):
        """
        Calculate the temperature for a dataframe of company data.

        Required columns:

        * target_reference_number: Int *x* of Abs *x*
        * scope: The scope of the target. This should be a valid scope in the SR15 mapping
        * scope_category: The scope category, options: "s1s2", "s3", "s1s2s3"
        * base_year: The base year of the target
        * start_year: The start year of the target
        * target_year: The year when the target should be achieved
        * time_frame: The time frame of the target (short, mid, long) -> This field is calculated by the target valuation protocol.
        * reduction_from_base_year: Targeted reduction in emissions from the base year
        * emissions_in_scope: Company emissions in the target's scope at start of the base year
        * achieved_reduction: The emission reduction that has already been achieved
        * industry: The industry the company is working in. This should be a valid industry in the SR15 mapping. If not it will be converted to "Others" (or whichever value is set in the config as the default).
        * s1s2_emissions: Total company emissions in the S1 + S2 scope
        * s3_emissions: Total company emissions in the S3 scope
        * market_cap: Market capitalization of the company. Only required to use the MOTS portfolio aggregation.
        * investment_value: The investment value of the investment in this company. Only required to use the MOTS, EOTS, ECOTS and AOTS portfolio aggregation.
        * company_enterprise_value: The enterprise value of the company. Only required to use the EOTS portfolio aggregation.
        * company_ev_plus_cash: The enterprise value of the company plus cash. Only required to use the ECOTS portfolio aggregation.
        * company_total_assets: The total assets of the company. Only required to use the AOTS portfolio aggregation.
        * company_revenue: The revenue of the company. Only required to use the ROTS portfolio aggregation.

        :param data: The data set
        :return: A data frame containing all relevant information for the targets and companies
        """
        data = self._prepare_data(data)
        data = self._calculate_company_score(data)
        return data

    def _get_aggregations(self, data: pd.DataFrame):
        data = data.copy()
        weighted_scores = self._calculate_aggregate_score(data, self.c.COLS.TEMPERATURE_SCORE,
                                                          self.aggregation_method)
        data[self.c.COLS.CONTRIBUTION_RELATIVE] = weighted_scores / (weighted_scores.sum() / 100)
        data[self.c.COLS.CONTRIBUTION] = weighted_scores

        # TODO: Move this into some kind of class
        return {"score": weighted_scores.sum(),
                "contributions": data.sort_values(
                    self.c.COLS.CONTRIBUTION_RELATIVE, ascending=False)[self.c.CONTRIBUTION_COLUMNS].to_dict(
                    orient="records")}, \
            data[self.c.COLS.CONTRIBUTION_RELATIVE], \
            data[self.c.COLS.CONTRIBUTION]

    def aggregate_scores(self, data: pd.DataFrame, time_frames: Optional[List[str]] = None,
                         scope_categories: Optional[List[str]] = None):
        """
        Aggregate scores to create a portfolio score per time_frame (short, mid, long).

        :param data: The results of the calculate method
        :param time_frames: A list of time frames that should be calculated (if None or an empty list is passed, all scopes will be calculated)
        :param scope_categories: A list of scope categories that should be calculated (if None or an empty list is passed, all scopes will be calculated)
        :return: A weighted temperature score for the portfolio
        """
        if time_frames is None or len(time_frames) == 0:
            time_frames = data[self.c.COLS.TIME_FRAME].unique()
        if scope_categories is None or len(scope_categories) == 0:
            scope_categories = data[self.c.COLS.SCOPE_CATEGORY].unique()

        portfolio_scores: Dict = {
            time_frame: {scope: {} for scope in scope_categories}
            for time_frame in time_frames}

        for time_frame, scope in itertools.product(time_frames, scope_categories):
            filtered_data = data[(data[self.c.COLS.TIME_FRAME] == time_frame) &
                                 (data[self.c.COLS.SCOPE_CATEGORY] == scope)].copy()

            if not filtered_data.empty:
                portfolio_scores[time_frame][scope]["all"],\
                    filtered_data[self.c.COLS.CONTRIBUTION_RELATIVE],\
                    filtered_data[self.c.COLS.CONTRIBUTION] = self._get_aggregations(filtered_data)

                portfolio_scores[time_frame][scope]["influence_percentage"] = self._calculate_aggregate_score(
                    filtered_data, self.c.TEMPERATURE_RESULTS, self.aggregation_method).sum() * 100

                # If there are grouping column(s) we'll group in pandas and pass the results to the aggregation
                if len(self.grouping) > 0:
                    grouped_data = filtered_data.groupby(self.grouping)
                    for group_name, group in grouped_data:
                        group_name_joined = group_name if type(group_name) == str else "-".join(group_name)
                        portfolio_scores[time_frame][scope][group_name_joined], _, _ = \
                            self._get_aggregations(group.copy())
            else:
                portfolio_scores[time_frame][scope] = None

        return portfolio_scores

    def columns_percentage_distribution(self, data: pd.DataFrame, columns: List[str]) -> Optional[dict]:
        """
        Percentage distribution of specific column or columns

        :param data: output from the target_validation
        :param columns: specified column names the client would like to have a percentage distribution
        :return: percentage distribution of specified columns
        """
        data = data[columns].fillna('unknown')
        if columns is None:
            return None
        elif len(columns) == 1:
            percentage_distribution = round((data.groupby(columns[0]).size() / data[columns[0]].count()) * 100, 2)
            return percentage_distribution.to_dict()
        elif len(columns) > 1:
            percentage_distribution = round((data.groupby(columns).size() / data[columns[0]].count()) * 100, 2)
            percentage_distribution = percentage_distribution.to_dict()

            percentage_distribution_copy = percentage_distribution.copy()
            # Modifies the original key name (tuple) into string representation
            for key, value in percentage_distribution_copy.items():
                key_combined = key if type(key) == str else "-".join(key)
                percentage_distribution[key_combined] = percentage_distribution[key]
                del percentage_distribution[key]
            return percentage_distribution

    def cap_scores(self, scores: pd.DataFrame) -> pd.DataFrame:
        """
        Cap the temperature scores in the input data frame to a certain value, based on the scenario that's being used. 
        This can either be for the whole data set, or only for the top X contributors.

        :param scores: The data set with the temperature scores
        :return: The input data frame, with capped scores
        """
        if self.scenario is None:
            return scores
        if self.scenario.scenario_type == ScenarioType.APPROVED_TARGETS:
            score_based_on_target = ~pd.isnull(scores[self.c.COLS.TARGET_REFERENCE_NUMBER])
            scores.loc[score_based_on_target, self.c.COLS.TEMPERATURE_SCORE] = \
                scores.loc[score_based_on_target, self.c.COLS.TEMPERATURE_SCORE].apply(
                    lambda x: min(x, self.scenario.get_score_cap()))
        elif self.scenario.scenario_type == ScenarioType.HIGHEST_CONTRIBUTORS:
            # Cap scores of 10 highest contributors per time frame-scope combination
            # TODO: Should this actually be per time-frame/scope combi? Aren't you engaging the company as a whole?
            aggregations = self.aggregate_scores(scores)
            for time_frame in self.c.VALUE_TIME_FRAMES:
                for scope in scores[self.c.COLS.SCOPE_CATEGORY].unique():
                    number_top_contributors = min(10, len(aggregations[time_frame][scope]['all']['contributions']))
                    for contributor in range(number_top_contributors):
                        company_name = aggregations[time_frame][scope]['all']['contributions'][contributor][
                            self.c.COLS.COMPANY_NAME]
                        company_mask = ((scores[self.c.COLS.COMPANY_NAME] == company_name) &
                                        (scores[self.c.COLS.SCOPE_CATEGORY] == scope) &
                                        (scores[self.c.COLS.TIME_FRAME] == time_frame))
                        scores.loc[company_mask, self.c.COLS.TEMPERATURE_SCORE] = \
                            scores.loc[company_mask, self.c.COLS.TEMPERATURE_SCORE].apply(
                                lambda x: min(x, self.scenario.get_score_cap()))
        elif self.scenario.scenario_type == ScenarioType.HIGHEST_CONTRIBUTORS_APPROVED:
            scores[self.c.COLS.ENGAGEMENT_TARGET] = scores[self.c.COLS.ENGAGEMENT_TARGET] == True
            score_based_on_target = scores[self.c.COLS.ENGAGEMENT_TARGET]
            scores.loc[score_based_on_target, self.c.COLS.TEMPERATURE_SCORE] = \
                scores.loc[score_based_on_target, self.c.COLS.TEMPERATURE_SCORE].apply(
                    lambda x: min(x, self.scenario.get_score_cap()))
        return scores

    def anonymize_data_dump(self, scores: pd.DataFrame) -> pd.DataFrame:
        """
        Anonymize the scores by deleting the company IDs (ISIC) and renaming the companies.

        :param scores: The data set with the temperature scores
        :return: The input data frame, anonymized
        """
        scores.drop(columns=[self.c.COLS.COMPANY_ISIC, self.c.COLS.COMPANY_ID], inplace=True)
        for index, company_name in enumerate(scores[self.c.COLS.COMPANY_NAME].unique()):
            scores.loc[scores[self.c.COLS.COMPANY_NAME] == company_name, self.c.COLS.COMPANY_NAME] = 'Company' + str(
                index + 1)
        return scores
