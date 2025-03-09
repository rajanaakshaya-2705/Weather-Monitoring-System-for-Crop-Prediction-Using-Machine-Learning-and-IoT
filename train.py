import pandas as pd # type: ignore
from sklearn.model_selection import train_test_split # type: ignore
from sklearn.tree import DecisionTreeClassifier # type: ignore
from sklearn.metrics import accuracy_score # type: ignore
from sklearn.preprocessing import LabelEncoder # type: ignore
import joblib # type: ignore

# Load the dataset (assuming it's an Excel file)
df = pd.read_excel('crops_data.xlsx')

# Print out the column names to verify
print("Columns in the dataset:", df.columns)

# Features and target variable
# Adjust column names based on the output from df.columns
X = df[['year', 'date_of_year', 'temperature', 'humidity', 'soil_moisture', 'rainfall']]
y = df['crop_type']

# Encode the target variable (crop_type) into numerical values
le = LabelEncoder()
y_encoded = le.fit_transform(y)

# Split the dataset into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2, random_state=42)

# Initialize the Decision Tree Classifier
model = DecisionTreeClassifier()

# Train the model
model.fit(X_train, y_train)

# Make predictions on the test set
y_pred = model.predict(X_test)

# Evaluate the model
accuracy = accuracy_score(y_test, y_pred)
print(f"Accuracy: {accuracy}")

# Save the trained model to a file
joblib.dump(model, 'crop_type_prediction_model.pkl')

# Save the label encoder to decode the predictions
joblib.dump(le, 'label_encoder.pkl')