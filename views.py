from django.http import HttpResponse 
from django.shortcuts import render
import os
import pandas as pd
import numpy as np
import json
import yfinance as yf
import warnings
from datetime import datetime, timedelta

# Suppress specific FutureWarning
warnings.filterwarnings("ignore", category=FutureWarning, message=".*TimedeltaIndex construction is deprecated.*")

periods = {
        '1Day': timedelta(days=1),
        '1Week': timedelta(weeks=1),
        '1Month': timedelta(days=30),
        '3Months': timedelta(days=90),
        '6Months': timedelta(days=180),
        '1Year': timedelta(days=365),
        '5Years': timedelta(days=5*365)
    }

# Function to calculate returns for a given stock data
def calculate_returns(stock_data):
    returns = {}

    if stock_data.empty:
        return {period: None for period in periods.keys()}

    last_trading_day = stock_data.index[-1]
    current_close = stock_data['Close'].loc[last_trading_day]

    for period, delta in periods.items():
        target_date = last_trading_day - delta
        past_data = stock_data[stock_data.index <= target_date]

        if not past_data.empty:
            past_close = past_data['Close'].iloc[-1]
            returns[period] = round(((current_close - past_close) / past_close) * 100, 2)
        else:
            returns[period] = None

    return returns

# Main function to fetch data and calculate returns for all companies in the DataFrame
def fetch_all_company_data(df):
    monthly_returns = pd.DataFrame()
    # Define periods and labels

    # Iterate through each row of the DataFrame
    for index, row in df.iterrows():
        symbol = row['NSEID'] + ".NS"  # Append ".NS" to the symbol

        # Fetch data for the company using yfinance
        # end_date = datetime.today().strftime('%Y-%m-%d')
        # start_date = (datetime.today() - timedelta(days=6*365)).strftime('%Y-%m-%d')
        # stock_data = yf.download(symbol, start=start_date, end=end_date)
        tick = yf.Ticker(symbol)
        stock_data = tick.history(period='6y')

        # Resample the data monthly and calculate percentage change
        mreturns = stock_data['Close'].resample('ME').ffill().pct_change()

        # Check if monthly_returns DataFrame exists
        if 'monthly_returns' not in locals():
            # If not, create a new DataFrame with the returns series
            monthly_returns = pd.DataFrame(mreturns)
        else:
        # If exists, concatenate the returns series with it
            monthly_returns = pd.concat([monthly_returns, mreturns], axis=1)

        # Update the DataFrame with the closing price of the last trading day
        df.at[index, 'Price'] = round(stock_data['Close'].iloc[-1],2)
        
        # Calculate returns for the company
        returns = calculate_returns(stock_data)
        
        # Update DataFrame with the fetched data
        for period, value in returns.items():
            df.at[index, period] = value
        

    return df, monthly_returns

def comp_df(ind):
    path = os.path.join('static', 'Name_Ind_NSEID.xlsx')
    df = pd.read_excel(path)
    
    # Filtering the dataframe
    new_df = df[df['Ind'] == ind].reset_index(drop=True)

    # Define a function to determine the value of 'YCode'
    def get_ycode(row):
        return str(row['NSEID']) + '.NS'

    # Apply the function to create the 'YCode' column
    new_df['YCode'] = new_df.apply(get_ycode, axis=1)

    # Define a function to fetch market data from yfinance
    def YData(row):
        try:
            ticker = yf.Ticker(row['YCode'])
            info = ticker.info
            market_cap = round(info['marketCap'] / 10000000) if info['marketCap'] is not None else None
            pe_ratio = round(info.get('forwardPE', ""), 2) if info.get('forwardPE', "") else None
            city = info.get('city', "") if info.get('city', "") else None
            return market_cap, pe_ratio, city
        except Exception as e:
            return None, None, None

    # Apply the function to each row and expand the result into new columns
    new_df[['MarketCap', 'PERatio', 'City']] = new_df.apply(YData, axis=1, result_type='expand')

    # Remove rows where 'MarketCap' column is None
    new_df = new_df[new_df['MarketCap'].notnull()]

    # Sort the DataFrame by 'MarketCap' column from max to min
    new_df = new_df.sort_values(by='MarketCap', ascending=False)

    # Fetch data for all companies in the DataFrame and print the result
    new_df, monthly_returns = fetch_all_company_data(new_df)

    # Dropping columns 'Ind' and 'NSEID'
    new_df = new_df.drop(columns=['Ind', 'NSEID', 'YCode'])

    # Reset the index of the DataFrame
    new_df = new_df.reset_index(drop=True)
    
    return new_df, monthly_returns

def HomePage(request):
    path = os.path.join('static', 'All_YInd.xlsx')
    all_ind_df = pd.read_excel(path)

    # Convert the "Ind" column to a list
    categories = all_ind_df['Ind'].tolist()

    selected_category = request.GET.get('category','Oil & Gas Refining & Marketing')

    ind ="Oil & Gas Refining & Marketing"
    comp_data, monthly_returns = comp_df(selected_category) 

    # Convert the DataFrame to a list of dictionaries for easier rendering
    data = comp_data.to_dict(orient='records')

    # Define a function to apply the custom color scale
    def color_negative_red(val):
        color = 'green' if val >= 0 else 'red'
        return f'background-color: {color}'

    def background_gradient(s, m, M, cmap='RdYlGn', low=0, high=0):
        rng = M - m
        norm = (s - m) / rng
        norm = norm.clip(low, high)
        c = [mpl.colors.rgb2hex(x) for x in plt.cm.get_cmap(cmap)(norm)]
        return ['background-color: %s' % color for color in c]

    # Apply the color scale
    # styled_df = monthly_returns.style.applymap(color_negative_red).background_gradient(cmap='RdYlGn', axis=None)

    # Render the styled DataFrame to HTML
    # html_table = styled_df.to_html()
    html_table = monthly_returns.to_html()

    
    # indices
    # Fetch historical market data for the last 6 years
    index = yf.Ticker('^NSEI')
    hist = index.history(period="6y")
    retIndex = calculate_returns(hist)
    # Add the last trading day price to the dictionary
    retIndex['Price'] = round(hist['Close'].iloc[-1],2)

    # Pass the DataFrame data as context to the template
    return render(request, 'index.html', {'data': data, 'categories': categories, 'selected_category': selected_category, 'html_table': html_table, 'retIndex': retIndex})

def about(request):
    # ind ="aquaculture"
    # comp_data = comp_df(ind)

    # # For demonstration, let's convert the DataFrame to an HTML table
    # html_table = comp_data.to_html()

    # # Render the HTML table in a template (or directly in an HttpResponse for simplicity)
    # return HttpResponse(html_table)

    # return render(request,"about.html")


    # Create a sample DataFrame
    data = np.random.randn(10, 4)  # 10 rows, 4 columns of random numbers including negatives
    df = pd.DataFrame(data, columns=['A', 'B', 'C', 'D'])

    # Define a function to apply the custom color scale
    def color_negative_red(val):
        color = 'green' if val >= 0 else 'red'
        return f'background-color: {color}'

    def background_gradient(s, m, M, cmap='RdYlGn', low=0, high=0):
        rng = M - m
        norm = (s - m) / rng
        norm = norm.clip(low, high)
        c = [mpl.colors.rgb2hex(x) for x in plt.cm.get_cmap(cmap)(norm)]
        return ['background-color: %s' % color for color in c]

    # Apply the color scale
    styled_df = df.style.applymap(color_negative_red).background_gradient(cmap='RdYlGn', axis=None)

    # Render the styled DataFrame to HTML
    html_table = styled_df.to_html()

    # Pass the HTML to the template
    return render(request, 'about.html', {'html_table': html_table})
    
# def stockName(request,stockName=None):
#     folder_path = r'E:\KHAZMUDDIN\BTECH\PYTHON\py_projects\PyStock\Industries'
#     all_comp_data = pd.read_excel(folder_path + "/all_companies_info.xlsx")
#     # Retrieve the row as a dictionary
#     row_dict = all_comp_data[all_comp_data.iloc[:, 0] == stockName].to_dict(orient='records')
#     if row_dict:
#         row_dict = row_dict[0]  # Get the first match as dictionary
#     else:
#         row_dict = None  # No match found
#     return render(request,"stock.html",row_dict)

# def stockName(request,stockName=None):
#     if(stockName!=None):
#         stockName = stockName + ".NS"
#         ticker = yf.Ticker(stockName)
#         info = ticker.info
#         # print(info)
#         # print(info['marketCap'])
#         # print(info['longBusinessSummary'])
#         row_dict = {
#             "Name": stockName,
#             "MCap": info['marketCap'],
#             "BSummary": info['longBusinessSummary']
#         }
#     else:
#         row_dict = {}
#     return render(request,"stock.html",row_dict)

def stockName(request):
    try:
        stockName = request.GET['inputText']
        stockName = stockName + ".NS"
        ticker = yf.Ticker(stockName)
        info = ticker.info
        row_dict = {
            "Name": stockName,
            "MCap": info['marketCap'],
            "BSummary": info['longBusinessSummary']
        }
    except:
        row_dict = {}
    return render(request,"stock.html",row_dict)

# data = {
#     'address1': 'Maker Chambers IV',
#     'address2': '3rd Floor 222 Nariman Point',
#     'city': 'Mumbai',
#     'zip': '400021',
#     'country': 'India',
#     'phone': '91 22 3555 5000',
#     'fax': '91 22 2204 2268',
#     'website': 'https://www.ril.com',
#     'industry': 'Oil & Gas Refining & Marketing',
#     'industryKey': 'oil-gas-refining-marketing',
#     'industryDisp': 'Oil & Gas Refining & Marketing',
#     'sector': 'Energy',
#     'sectorKey': 'energy',
#     'sectorDisp': 'Energy',
#     'companyOfficers': [
#         {
#             'maxAge': 1,
#             'name': 'Mr. Mukesh Dhirubhai Ambani',
#             'age': 66,
#             'title': 'Chairman & MD',
#             'yearBorn': 1957,
#             'fiscalYear': 2023,
#             'exercisedValue': 0,
#             'unexercisedValue': 0
#         },
#         {
#             'maxAge': 1,
#             'name': 'Mr. Srikanth  Venkatachari',
#             'age': 57,
#             'title': 'Chief Financial Officer',
#             'yearBorn': 1966,
#             'fiscalYear': 2023,
#             'exercisedValue': 0,
#             'unexercisedValue': 0
#         },
#         {
#             'maxAge': 1,
#             'name': 'Ms. Savithri  Parekh',
#             'title': 'Company Secretary & Compliance Officer',
#             'fiscalYear': 2023,
#             'exercisedValue': 0,
#             'unexercisedValue': 0
#         },
#         {
#             'maxAge': 1,
#             'name': 'Mr. Nikhil Rasiklal Meswani',
#             'age': 57,
#             'title': 'Executive Director',
#             'yearBorn': 1966,
#             'fiscalYear': 2023,
#             'totalPay': 250000000,
#             'exercisedValue': 0,
#             'unexercisedValue': 0
#         },
#         {
#             'maxAge': 1,
#             'name': 'Mr. Hital Rasiklal Meswani',
#             'age': 55,
#             'title': 'Executive Director',
#             'yearBorn': 1968,
#             'fiscalYear': 2023,
#             'totalPay': 250000000,
#             'exercisedValue': 0,
#             'unexercisedValue': 0
#         },
#         {
#             'maxAge': 1,
#             'name': 'Mr. Panda Madhusudana Siva Prasad',
#             'age': 71,
#             'title': 'Executive Director',
#             'yearBorn': 1952,
#             'fiscalYear': 2023,
#             'totalPay': 135000000,
#             'exercisedValue': 0,
#             'unexercisedValue': 0
#         },
#         {
#             'maxAge': 1,
#             'name': 'Ms. Parul  Sharma',
#             'title': 'Group President',
#             'fiscalYear': 2023,
#             'exercisedValue': 0,
#             'unexercisedValue': 0
#         },
#         {
#             'maxAge': 1,
#             'name': 'Mr. Jyotindra Hiralal Thacker',
#             'title': 'President of Technology',
#             'fiscalYear': 2023,
#             'exercisedValue': 0,
#             'unexercisedValue': 0
#         },
#         {
#             'maxAge': 1,
#             'name': 'Mr. Hemen Kanu Modi',
#             'title': 'Vice President of Investor Relations',
#             'fiscalYear': 2023,
#             'exercisedValue': 0,
#             'unexercisedValue': 0
#         },
#         {
#             'maxAge': 1,
#             'name': 'Mr. Rohit  Bansal',
#             'title': 'Group Head of Communications',
#             'fiscalYear': 2023,
#             'exercisedValue': 0,
#             'unexercisedValue': 0
#         }
#     ],
#     'auditRisk': 6,
#     'boardRisk': 9,
#     'compensationRisk': 7,
#     'shareHolderRightsRisk': 1,
#     'overallRisk': 9,
#     'governanceEpochDate': 1714521600,
#     'compensationAsOfEpochDate': 1703980800,
#     'irWebsite': 'http://ril.com/html/investor/investor.html',
#     'maxAge': 86400,
#     'priceHint': 2,
#     'previousClose': 2932.5,
#     'open': 2936.0,
#     'dayLow': 2933.2,
#     'dayHigh': 2957.0,
#     'regularMarketPreviousClose': 2932.5,
#     'regularMarketOpen': 2936.0,
#     'regularMarketDayLow': 2933.2,
#     'regularMarketDayHigh': 2957.0,
#     'dividendRate': 9.0,
#     'dividendYield': 0.0031,
#     'exDividendDate': 1692576000,
#     'payoutRatio': 0.0875,
#     'fiveYearAvgDividendYield': 0.44,
#     'beta': 0.599,
#     'trailingPE': 28.5631,
#     'forwardPE': 40.918583,
#     'volume': 1579597,
#     'regularMarketVolume': 1579597,
#     'averageVolume': 5699520,
#     'averageVolume10days': 4493922,
#     'averageDailyVolume10Day': 4493922,
#     'bid': 2941.0,
#     'ask': 2941.15,
#     'bidSize': 0,
#     'askSize': 0,
#     'marketCap': 20082287706112,
#     'fiftyTwoWeekLow': 2220.3,
#     'fiftyTwoWeekHigh': 3024.9,
#     'priceToSalesTrailing12Months': 2.2287304,
#     'fiftyDayAverage': 2909.058,
#     'twoHundredDayAverage': 2648.935,
#     'trailingAnnualDividendRate': 10.0,
#     'trailingAnnualDividendYield': 0.0034100597,
#     'currency': 'INR',
#     'enterpriseValue': 22591242764288,
#     'profitMargins': 0.07727,
#     'floatShares': 3292169614,
#     'sharesOutstanding': 6766110208,
#     'heldPercentInsiders': 0.49653998,
#     'heldPercentInstitutions': 0.28054002,
#     'impliedSharesOutstanding': 6830709760,
#     'bookValue': 1172.783,
#     'priceToBook': 2.5068576,
#     'lastFiscalYearEnd': 1711843200,
#     'nextFiscalYearEnd': 1743379200,
#     'mostRecentQuarter': 1711843200,
#     'earningsQuarterlyGrowth': -0.018,
#     'netIncomeToCommon': 696210030592,
#     'trailingEps': 102.93,
#     'forwardEps': 71.85,
#     'lastSplitFactor': '2:1',
#     'lastSplitDate': 1504742400,
#     'enterpriseToRevenue': 2.507,
#     'enterpriseToEbitda': 13.925,
#     '52WeekChange': 0.26079524,
#     'SandP52WeekChange': 0.26137078,
#     'lastDividendValue': 9.0,
#     'lastDividendDate': 1692576000,
#     'exchange': 'NSI',
#     'quoteType': 'EQUITY',
#     'symbol': 'RELIANCE.NS',
#     'underlyingSymbol': 'RELIANCE.NS',
#     'shortName': 'RELIANCE INDS',
#     'longName': 'Reliance Industries Limited',
#     'firstTradeDateEpochUtc': 820467900,
#     'timeZoneFullName': 'Asia/Kolkata',
#     'timeZoneShortName': 'IST',
#     'uuid': '6fb3aba7-25b9-3826-85a7-5fb8a94f4e84',
#     'messageBoardId': 'finmb_878373',
#     'gmtOffSetMilliseconds': 19800000,
#     'currentPrice': 2940.0,
#     'targetHighPrice': 2830.0,
#     'targetLowPrice': 1350.0,
#     'targetMeanPrice': 2272.1,
#     'targetMedianPrice': 2280.0,
#     'recommendationMean': 2.1,
#     'recommendationKey': 'buy',
#     'numberOfAnalystOpinions': 29,
#     'totalCash': 2033949999104,
#     'totalCashPerShare': 300.622,
#     'ebitda': 1622330048512,
#     'totalDebt': 3461419892736,
#     'quickRatio': 0.591,
#     'currentRatio': 1.183,
#     'totalRevenue': 9010640060416,
#     'debtToEquity': 37.389,
#     'revenuePerShare': 1331.775,
#     'returnOnAssets': 0.0414,
#     'returnOnEquity': 0.09007,
#     'freeCashflow': -559001239552,
#     'operatingCashflow': 1587880001536,
#     'earningsGrowth': -0.018,
#     'revenueGrowth': 0.111,
#     'grossMargins': 0.35039002,
#     'ebitdaMargins': 0.18004999,
#     'operatingMargins': 0.122379996,
#     'financialCurrency': 'INR',
#     'trailingPegRatio': None
# }

