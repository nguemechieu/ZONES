import joblib as joblib

import pandas as pd
import os

from openai.api_resources import engine
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.neural_network import MLPClassifier

# GET DATA FROM ZONES DATABASE

db = pd.read_sql_query('SELECT * FROM zones', con=engine)
df = pd.DataFrame(db)
exists = os.path.isfile("src/saved_model.pkl")
if exists:
    os.remove('src/saved_model.pkl')

columns = ['price', 'open', 'high', 'low', 'close', 'volume', 'time']
# //'MA', 'STO', 'FIBO', 'AC', 'BUL', 'ICCI', 'MACD', 'RSI','BEAR','AD','ATR','AO','MOM','OSMA']
labels = df['price'].values
features = df[list(columns)].values

X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.05)

clf = MLPClassifier(hidden_layer_sizes=(100, 100, 100))
clf = clf.fit(X_train, y_train)

accuracy = clf.sscore(X_train, y_train)
print(' traning data accuracy ', accuracy * 100)

accuracy = clf.score(X_test, y_test)
print(' testing data accuracy ', accuracy * 100)

ypredict = clf.predict(X_train)
print('\n Training classification report\n', classification_report(y_train, ypredict))

ypredict = clf.predict(X_test)
print('\n Testing classification report\n', classification_report(y_test, ypredict))

# Output a pickle file for the model
joblib.dump(clf, 'src/saved_model.pkl')
