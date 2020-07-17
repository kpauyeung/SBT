import os
import unittest

import pandas as pd
from SBTi.temperature_score import TemperatureScore
from SBTi.portfolio_aggregation import PortfolioAggregationMethod


class TestTemperatureScore(unittest.TestCase):
    """
    Test the reporting functionality. We'll use the Example data provider as the output of this provider is known in
    advance.
    """

    def setUp(self) -> None:
        """
        Create the provider and reporting instance which we'll use later on.
        :return:
        """
        self.temperature_score = TemperatureScore()
        self.data = pd.read_csv(os.path.join(os.path.dirname(os.path.realpath(__file__)), "inputs",
                                             "data_test_temperature_score.csv"))

    def test_temp_score(self) -> None:
        """
        Test whether the temperature score is calculated as expected.

        :return:
        """
        scores = self.temperature_score.calculate(self.data)
        self.assertAlmostEqual(scores[
                   (scores["company_name"] == "Company T") &
                   (scores["scope_category"] == "s1s2")
               ]["temperature_score"].iloc[0], 1.7699, places=4, msg="The temp score was incorrect")
        self.assertAlmostEqual(scores[
                   (scores["company_name"] == "Company E") &
                   (scores["scope_category"] == "s1s2")
               ]["temperature_score"].iloc[0], 3.2, places=4, msg="The fallback temp score was incorrect")
        self.assertAlmostEqual(scores[
                   (scores["company_name"] == "Company AA") &
                   (scores["time_frame"] == "mid") &
                   (scores["scope_category"] == "s1s2s3")
               ]["temperature_score"].iloc[0], 1.9075, places=4, msg="The aggregated temp score was incorrect")
        self.assertAlmostEqual(scores[
                   (scores["company_name"] == "Company AA") &
                   (scores["time_frame"] == "long") &
                   (scores["scope_category"] == "s1s2s3")
               ]["temperature_score"].iloc[0], 3.2, places=5, msg="The aggregated fallback temp score was incorrect")

    def test_portfolio_aggregations(self):
        scores = self.temperature_score.calculate(self.data)
        aggregations = self.temperature_score.aggregate_scores(scores, PortfolioAggregationMethod.WATS)
        self.assertAlmostEqual(aggregations["short"]['s1s2']["all"]["score"], 3.0357, places=4, msg="Short WATS aggregation failed")
        self.assertAlmostEqual(aggregations["mid"]['s1s2']["all"]["score"], 2.8163, places=4, msg="Mid WATS aggregation failed")
        self.assertAlmostEqual(aggregations["long"]['s1s2']["all"]["score"], 3.2000, places=4, msg="Long WATS aggregation failed")
        aggregations = self.temperature_score.aggregate_scores(scores, PortfolioAggregationMethod.TETS)
        self.assertAlmostEqual(aggregations["short"]['s1s2']["all"]["score"], 2.8828, places=4, msg="Short TETS aggregation failed")
        self.assertAlmostEqual(aggregations["mid"]['s1s2']["all"]["score"], 2.8998, places=4, msg="Mid TETS aggregation failed")
        self.assertAlmostEqual(aggregations["long"]['s1s2']["all"]["score"], 3.2000, places=4, msg="Long TETS aggregation failed")
        aggregations = self.temperature_score.aggregate_scores(scores, PortfolioAggregationMethod.MOTS)
        self.assertAlmostEqual(aggregations["short"]['s1s2']["all"]["score"], 2.8844, places=4, msg="Short MOTS aggregation failed")
        self.assertAlmostEqual(aggregations["mid"]['s1s2']["all"]["score"], 2.8766, places=4, msg="Mid MOTS aggregation failed")
        self.assertAlmostEqual(aggregations["long"]['s1s2']["all"]["score"], 3.2000, places=4, msg="Long MOTS aggregation failed")
        aggregations = self.temperature_score.aggregate_scores(scores, PortfolioAggregationMethod.EOTS)
        self.assertAlmostEqual(aggregations["short"]['s1s2']["all"]["score"], 2.9368, places=4, msg="Short EOTS aggregation failed")
        self.assertAlmostEqual(aggregations["mid"]['s1s2']["all"]["score"], 2.8853, places=4, msg="Mid EOTS aggregation failed")
        self.assertAlmostEqual(aggregations["long"]['s1s2']["all"]["score"], 3.2000, places=4, msg="Long EOTS aggregation failed")
        aggregations = self.temperature_score.aggregate_scores(scores, PortfolioAggregationMethod.ECOTS)
        self.assertAlmostEqual(aggregations["short"]['s1s2']["all"]["score"], 2.8844, places=4, msg="Short ECOTS aggregation failed")
        self.assertAlmostEqual(aggregations["mid"]['s1s2']["all"]["score"], 2.8766, places=4, msg="Mid ECOTS aggregation failed")
        self.assertAlmostEqual(aggregations["long"]['s1s2']["all"]["score"], 3.2000, places=4, msg="Long ECOTS aggregation failed")
        aggregations = self.temperature_score.aggregate_scores(scores, PortfolioAggregationMethod.AOTS)
        self.assertAlmostEqual(aggregations["short"]['s1s2']["all"]["score"], 2.8844, places=4, msg="Short AOTS aggregation failed")
        self.assertAlmostEqual(aggregations["mid"]['s1s2']["all"]["score"], 2.8766, places=4, msg="Mid AOTS aggregation failed")
        self.assertAlmostEqual(aggregations["long"]['s1s2']["all"]["score"], 3.2000, places=4, msg="Long AOTS aggregation failed")


if __name__ == "__main__":
    test = TestTemperatureScore()
    test.setUp()
    test.test_temp_score()
    test.test_portfolio_aggregations()



# testing
# import pandas as pd
# import os
#
# data = pd.read_csv(os.path.join("C:/Projects/SBTi/test/inputs/data_test_temperature_score.csv"))
# temperature_score = TemperatureScore()
# scores = temperature_score.calculate(data)
# aggregations = temperature_score.aggregate_scores(scores, PortfolioAggregationMethod.TETS)



