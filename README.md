# Sales Performance & Analytics Dashboard

A modern, production-ready Sales Analytics Dashboard built with **Flask**, **Pandas**, **Matplotlib**, and **Seaborn** backend and an **Inter/Fraunces** responsive front-end.

---

## 🚀 Features

- **User Authentication**: Secure Sign In and Account Registration using SQLite, salted password hashing (`werkzeug.security`), and HTTP-only session cookies.
- **Dynamic Executive KPIs**: Total Revenue, Total Orders, Unique Customers, Average Order Value (AOV), and Order Completion Rate.
- **Server-Side Visualizations**: Generated on the fly with Matplotlib & Seaborn:
  - Monthly Revenue Trend (Line chart)
  - Revenue by City (Highlighted ranking chart)
  - Revenue by Product Category (Horizontal bar chart)
  - Payment Method distribution (Pie chart)
  - Customer Segment distribution (Bar chart)
  - Order Status breakdown (Completed vs. Cancelled vs. Returned)
- **Top Products Leaderboard**: Interactive ranking with dynamic progress bars.
- **Interactive City Filtering**: Filter all metrics, charts, and tables dynamically by city.
- **CSV Dataset Upload**: Upload new datasets directly from the UI with real-time schema validation.

---

## 📁 Project Structure

```
├── app.py                  # Main Flask application & analytics API
├── data.csv                # Primary sales dataset
├── requirements.txt        # Python production dependencies
├── Procfile                # WSGI process configuration for Render/Heroku
├── render.yaml             # Render Blueprint configuration
├── runtime.txt             # Python runtime specification
├── pages/
│   ├── login.html          # Authentication page (Sign in / Register)
│   └── dashboard.html      # Main analytics dashboard
└── users.db                # SQLite database for user accounts
```

---

## 💻 Local Setup & Running

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Application**:
   ```bash
   python app.py
   ```

3. **Open in Browser**:
   Navigate to [http://127.0.0.1:5000](http://127.0.0.1:5000) and register your account or sign in.

---

## 🌐 Deploy to Render

### Option A: Automatic via GitHub (Recommended)

1. **Push to GitHub**:
   - Create a new GitHub repository.
   - Push the contents of this folder to your repository.

2. **Deploy on Render**:
   - Go to [dashboard.render.com](https://dashboard.render.com) and click **New +** → **Web Service**.
   - Connect your GitHub repository.
   - Configure the following settings:
     - **Name**: `sales-analytics-dashboard` (or your choice)
     - **Runtime**: `Python`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn app:app --workers 2 --threads 4 --timeout 120`
     - **Plan**: `Free`
   - Under **Advanced / Environment Variables**, add:
     - `PYTHON_VERSION`: `3.11.9`
     - `SECRET_KEY`: *(any long random string for secure sessions)*
   - Click **Deploy Web Service**.

### Option B: Using Render Blueprint

Because this repository includes `render.yaml`, you can simply click **New +** → **Blueprint** on Render, select this repository, and Render will automatically configure the build and start commands.

---

## 📊 CSV Upload Requirements

When uploading a new dataset, ensure your CSV includes the following columns:
`OrderID`, `CustomerID`, `OrderDate`, `City`, `Category`, `ProductName`, `PaymentMethod`, `Status`, `CustomerSegment`, `Quantity`, `Sales`.
