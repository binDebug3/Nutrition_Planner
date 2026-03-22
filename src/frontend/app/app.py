import streamlit as st

# 1. THE LOGIN GATE
# For a quick start, we use a simple password. 
# You can swap this for Google Login later.


def check_password():
    if "password_correct" not in st.session_state:
        st.text_input("Enter Password", 
                      type="password", 
                      on_change=lambda: st.session_state.update(
                          password_correct=st.session_state.password == "my_secret_password"), 
                      key="password")
        return False
    return st.session_state["password_correct"]


if not check_password():
    st.stop()

# 2. THE DATABASE CONNECTION
# This connects to the URL you put in secrets.toml
conn = st.connection("postgresql", type="sql")

st.title("Nutrient Goal Finder")

# 3. THE UI & ALGORITHM
# Let's say you want to find foods high in Protein but low in Carbs
protein_target = st.slider("Minimum Protein (g)", 0, 50, 20)
carb_max = st.slider("Maximum Carbs (g)", 0, 100, 10)

if st.button("Find Foods"):
    # Note the double quotes for column names with spaces/commas
    query = f"""
        SELECT food_name, serving_size, "Protein", "Carbohydrate, by difference"
        FROM food_nutrition
        WHERE "Protein" >= {protein_target} 
        AND "Carbohydrate, by difference" <= {carb_max}
        ORDER BY "Protein" DESC
        LIMIT 20
    """
    
    df = conn.query(query)
    st.table(df)
