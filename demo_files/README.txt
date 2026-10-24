ChillPrint demo files - all real readings from an in-orchard sensor in a pistachio orchard near Terra Bella
(Wildeye station 'CA Pistachio # 5', via the UC FNRIC API). Upload any of them in step 3.

1_orchard_this-winter_daily.xlsx     this winter so far (52 days), daily low and high, Excel
2_orchard_last-winter_daily.csv      last winter (182 days, Sep 1 to Mar 1), daily low and high
3_orchard_last-winter_logger.csv     last winter, hourly logger export (4,368 readings, local clock,
                                     plus the sensor's humidity and battery columns, which ChillPrint ignores)
4_orchard_last-winter_notebook.xlsx  last winter as a hand-kept sheet with odd headers
                                     ('Coldest overnight', 'Warmest afternoon'): the AI reader works it out

5_orchard_last-winter_with-3-mistakes.csv  file 2 with three values changed ON PURPOSE to show the error checks:
                                     Dec 15 low set to -6, Jan 10 high set to 100, Feb 2 low set to 100.
                                     ChillPrint flags all three and sets them aside. Everything else is real.

Put the pin on the orchard (Terra Bella, about 35.96, -119.07) so the comparison with the stations is for the
same place.
