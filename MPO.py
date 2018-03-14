from __future__ import division
import pandas_datareader as pdr
from collections import defaultdict
import numpy as np
from numpy import dot, sqrt
import pandas as pd
import datetime
from scipy.stats import linregress
from scipy.optimize import minimize
import plotly
import plotly.plotly as py
import plotly.graph_objs as go
import re

"""
Mess:
    Market returns in pct: 
        self.market_returns = self.data[self.market_indecies].pct_change().mean(axis=0)
    Covariance in pct: 
        self.cov_matrix = self.data.pct_change().cov() 
"""

"""
TODO:
 - generate and plot sharpe-ratio of a whole bunch of random portfolio weight combinations
 - calculate and plot capital market line
    - page 333 in python finance book
    - First derivative of efficient frontier??
- ADD required return
- ADD sanity check to see if wndow size and window move matches

"""

class Calcualtion_pack():
    "L4NT0W"
    
    def __init__(self, stock_ticks=["AAPL","MMM"], market_indecies=['^GSPC',"^DJI"], 
                 start=datetime.datetime(1997, 1, 1), end=datetime.date.today(), 
                 risk_free_rate= 0.02, shorting_allowed=False, 
                 window_size=None, window_move=None):

        self.stock_ticks = stock_ticks
        self.market_indecies = market_indecies #Concatenate different markets indecies to get "real" market
                                                # Possibly do this with different weights
        self.start = start
        self.end = end
        self.risk_free_rate = risk_free_rate
        self.shorting_allowed=shorting_allowed
        self.window_move = window_move
        self.window_size = window_size



    def get_monthly_data(self):
        raw_data = pdr.DataReader(self.market_indecies + self.stock_ticks, 
                                  "google", self.start, self.end)
        adj_data = raw_data["Close"]
        self.data = adj_data.groupby(pd.Grouper(freq='MS')).mean() #adjusted monthly data


    def calculate_log_change(self):
        self.log_change_data = (np.log(self.data) - np.log(self.data).shift(1)).dropna()


    def calculate_covariance_and_var(self):
        self.cov_matrix = self.log_change_data.cov() * 12
        self.var = pd.Series(np.diag(self.cov_matrix), index=[self.cov_matrix.columns])
        

    def calculate_beta(self): #can be done vith linalg cov_matrix * var 
        #getting beta as covar/var
        d = defaultdict(list)
        for index in self.market_indecies:
            var = self.cov_matrix.loc[index,index]
            for tick in self.stock_ticks:
                covar = self.cov_matrix.loc[index,tick]
                d[index] += [covar/var]
        self.beta1 = pd.DataFrame(data=d, index=self.stock_ticks)

    
    def calculate_regress_params(self):
        #getting alpha and beta with linear regression
        a = defaultdict(list)
        b = defaultdict(list)
        
        for market in self.market_indecies:
            for tick in self.stock_ticks:
                slope, intercept, _, _, _ = linregress(self.log_change_data[tick], self.log_change_data[market])
                a[market] += [intercept]
                b[market] += [slope]
     
        self.alfa = pd.DataFrame(data=a, index=self.stock_ticks)
        self.beta = pd.DataFrame(data=b, index=self.stock_ticks)

                
    def calculate_expected_market_return(self):
        #Using plane mean value
        self.market_returns = self.log_change_data[self.market_indecies].mean()
        #scaling to yearly using eulers
        self.market_returns_yr = np.exp(self.market_returns*12)-1
        

    def calculate_exp_return(self):
        #Using CAPM
        self.exp_return = self.risk_free_rate + (self.market_returns-self.risk_free_rate)* self.beta
        self.exp_return_yr = np.exp(self.exp_return*12)-1

        
    def plot_efficient_portfolio():
        pass
    
    
    def solve_quadratic_weights_of_portfolio(self):
        """
            where:
                R is the vector of CAPM expected returns
                C is the var-covariance matrix
                W is the weights
        """            
        R = self.exp_return_yr.values
        C = self.cov_matrix.iloc[:-1,:-1].values
        W = R*0 + 1/len(R) #Initialize equal procent weights
        
        def quad_var(W, C):
            return dot(dot(W.T, C), W) # Quadratic expression to calculate portfolio risk
        
        def exp_return(W, R):
            return np.dot(W.T, R).sum() # Expectd_portfolio_return
        
        def fitness(W, R, C, r):
            # For given level of return r, find weights which minimizes
            # portfolio variance.
            
            Pm = exp_return(W, R)
            Pv = quad_var(W, C) 
            return Pv

        #Bounds (inequality constraints)
        b = [(0.,1.) for i in W] # weights between 0%..100%. -No shorting
        # Equality constraints
        h = ({'type':'eq', 'fun': lambda W: sum(W) -1.}, # Sum of weights = 100%
             {'type':'eq', 'fun': lambda W: exp_return(W, R) - r})  # equalizes portfolio return to r
        
        Rf = np.linspace(min(R), max(R), num=100)
        Vf, Wf = [], []
       
        for r in Rf:
            optimized = minimize(fitness, W, args=(R, C, r), method='SLSQP', #Sequential Least SQuares Programming 
                                 constraints=h, bounds=b)
            
            X = optimized.x
            Wf.append(X)
            Vx = quad_var(X,C)
            Vf.append(Vx)
        
        self.frontier_exp_return = Rf #Y axis of EFF
        self.frontier_risk = Vf #X axis of EFF
        self.frontier_weights = [[round(w*100,2) for w in ws] for ws in Wf] #TODO might be done directly in pandas
    
    
    def plot_EFF(self):
        X = self.frontier_risk
        Y = self.frontier_exp_return

        plotly.tools.set_credentials_file(username="TheVizWiz", api_key="92x5KNp4VDPBDGNtLR2l")

        def annotaions():
            PD = pd.DataFrame(self.frontier_weights, columns=self.stock_ticks)
            T = [re.sub(r'\n', "% -- ", re.sub(r'[ ]+', " ", PD.iloc[i].to_string() )) for i in PD.index]
            return T

        data = [go.Scatter(
            x=X,
            y=Y,
            mode='lines',
            marker = dict(colorscale="Electric"),
            text = annotaions()
        )]

        start = "{0}/{1}-{2}".format(self.start.day, self.start.month, self.start.year)
        end = "{0}/{1}-{2}".format(self.end.day, self.end.month, self.end.year)
        layout = go.Layout(
            title= "Efficent Frontier: from {} to {}".format(start, end),
            showlegend=False,
            hovermode= 'closest',
            yaxis = dict(title="Portfolio Return"),
            xaxis = dict(title="Portfolio Variance"),
            height=600,
            width=600,
        )

        fig = go.Figure(data=data, layout=layout)
        plot_url = py.plot(fig, filename='efficent_frontier')  
    
    
    def analyze_data(self):
        self.calculate_log_change()
        self.calculate_covariance_and_var()
        self.calculate_expected_market_return()
        self.calculate_beta()
        self.calculate_regress_params()
        self.calculate_exp_return()
        self.solve_quadratic_weights_of_portfolio()



    def run_pack(self):

        def one_window():
            self.get_monthly_data()
            self.analyze_data()
            self.plot_EFF()

        if self.window_size and self.window_move:

            def with_moving_window(func):
                def func_wrapper():

                    time = self.end - self.start
                    window = datetime.timedelta(days=self.window_size)
                    window_m = datetime.timedelta(days=self.window_move)
                    self.final_end = self.end

                    while time >= datetime.timedelta(1):
                        self.end = self.start + window
                        func()
                        self.start = self.start + window_m
                        time -= window_m

                return func_wrapper
           
            with_moving_window(one_window)()
            
        else:
            one_window()

if __name__ == '__main__':
  
    CP = Calcualtion_pack(stock_ticks=["AAPL","MMM","GOOGL"], 
                            market_indecies=['NDAQ'],
                            start=datetime.datetime(1999, 1, 1), 
                            end=datetime.datetime(2001,1,1), 
                            risk_free_rate= 0.02,
                            window_size=3650, 
                            window_move=365)
  
    CP.run_pack()
