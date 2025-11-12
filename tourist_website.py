import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import os
from geopy.geocoders import Nominatim

# Set page configuration
st.set_page_config(
    page_title="Explore India - Tourist Destinations",
    page_icon="🌍",
    layout="wide"
)

# Custom CSS for better styling and improved contrast
st.markdown("""
<style>
  
    .stApp {
        background-color: #0f172a !important; 
        color: #e6eef8 !important; 
    }

   
    .stApp * {
        color: #e6eef8 !important;
    }

    /* Card styles */
    .destination-card {
        background-color: #0b1220 !important; /* darker card */
        color: #e6eef8 !important;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.6);
    }

  
    .stButton>button {
        background-color: #2563eb !important; /* blue */
        color: #ffffff !important;
        border-radius: 6px !important;
        padding: 0.5rem 1rem !important;
        box-shadow: 0 2px 6px rgba(37,99,235,0.3) !important;
    }

    /* Inputs*/
    .stTextInput>div>div>input,
    .stSelectbox>div>div>div>div{
        background-color: #071021 !important;
        color: #e6eef8 !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 8px !important;
    }

    /* Headers */
    h1, h2, h3, .css-ffhzg2 {
        color: #f8fafc !important;
        font-weight: 700 !important;
    }

    /* Expander header */
    .stExpander > button {
        background-color: #0b1220 !important;
        color: #e6eef8 !important;
        border-radius: 6px !important;
    }

    /* Map container adjustments */
    .stFrame > iframe {
        border-radius: 8px !important;
    }

    /* Ensure small text remains legible */
    .stCaption, .stMarkdown, .stText {
        color: #dbeafe !important;
    }

</style>
""", unsafe_allow_html=True)

# Load data
@st.cache_data
def load_data():
    """
    Robust CSV loader that maps existing CSV headers to the app's expected columns.
    It tolerates the repo's current columns by mapping 'significance' -> description and 'type' -> popular_attractions.
    """
    try:
        df = pd.read_csv('destinations.csv', encoding='utf-8-sig')

        # Normalize column names: strip, lower, replace spaces with _
        orig_cols = list(df.columns)
        norm_cols = [str(c).strip().lower().replace(' ', '_') for c in orig_cols]
        df.rename(columns=dict(zip(orig_cols, norm_cols)), inplace=True)

        # Drop any unnamed index column (common when saving CSVs with index)
        df = df.loc[:, ~df.columns.str.startswith('unnamed')]

        # Synonyms for common alternate headers (extended to match your CSV)
        synonyms = {
            'name': ['name', 'destination', 'place', 'title', 'location'],
            'state': ['state', 'region', 'province'],
            'description': ['description', 'desc', 'details', 'about', 'significance'],
            'popular_attractions': ['popular_attractions', 'attractions', 'popular_attraction', 'attraction', 'type'],
            'image_url': ['image_url', 'image', 'image_link', 'imageurl', 'photo', 'photo_url'],
            'latitude': ['latitude', 'lat'],
            'longitude': ['longitude', 'lon', 'long', 'lng']
        }

        # Find and rename columns to the canonical names used in the app
        found = {}
        for canonical, options in synonyms.items():
            for opt in options:
                if opt in df.columns:
                    found[canonical] = opt
                    break

        rename_map = {found[k]: k for k in found}
        if rename_map:
            df.rename(columns=rename_map, inplace=True)

        #
        required_columns = ['name', 'state']
        missing_required = [c for c in required_columns if c not in df.columns]
        if missing_required:
            st.error(f"Error: Required column(s) not found in CSV file: {missing_required}. Available columns: {', '.join(df.columns)}")
            return None

        
        if 'description' not in df.columns:
           
            if 'significance' in df.columns:
                df['description'] = df['significance']
            elif 'type' in df.columns:
                df['description'] = df['type']
            else:
                df['description'] = ''

        if 'popular_attractions' not in df.columns:
            if 'type' in df.columns:
                df['popular_attractions'] = df['type']
            else:
                df['popular_attractions'] = ''

        if 'image_url' not in df.columns:
            df['image_url'] = ''

        # Drop rows missing essential info
        df = df.dropna(subset=['name', 'state'])

        # Convert lat/lon to numeric if present
        for coord in ('latitude', 'longitude'):
            if coord in df.columns:
                df[coord] = pd.to_numeric(df[coord], errors='coerce')

        return df

    except FileNotFoundError:
        st.error("destinations.csv not found. Please place destinations.csv in the app directory.")
        return None
    except pd.errors.EmptyDataError:
        st.error("destinations.csv is empty or invalid. Please check the file.")
        return None
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None


def main():
    st.title("🌍 Explore India - Tourist Destinations")
    st.write("Discover the most amazing places to visit in India")

    # Load data
    df = load_data()
    if df is None:
        st.warning("No data found. Please ensure destinations.csv exists with the required columns.")
        return

    # Sidebar for filters
    st.sidebar.header("🔍 Filters")

    # Universal search
    search_query = st.sidebar.text_input("Search destinations...")

    # State filter
    states = ['All'] + sorted(df['state'].unique().tolist())
    selected_state = st.sidebar.selectbox("Select State", states)

    # Apply filters
    filtered_df = df.copy()

    if search_query:
        mask = (
            df['name'].str.contains(search_query, case=False, na=False)
            | df['description'].str.contains(search_query, case=False, na=False)
            | df['popular_attractions'].str.contains(search_query, case=False, na=False)
        )
        filtered_df = filtered_df[mask]

    if selected_state != 'All':
        filtered_df = filtered_df[filtered_df['state'] == selected_state]

    # Display results
    st.header(f"🗺️ {len(filtered_df)} Destinations Found")

    # Create two columns for layout
    col1, col2 = st.columns([2, 1])

    with col1:
        # Display map if coordinates are available
        if 'latitude' in df.columns and 'longitude' in df.columns:
            st.subheader("Map View")
            if not filtered_df.empty:
                # Create a map centered on India
                m = folium.Map(location=[20.5937, 78.9629], zoom_start=5)

                # Add markers for each destination
                for idx, row in filtered_df.iterrows():
                    if pd.notnull(row.get('latitude')) and pd.notnull(row.get('longitude')):
                        folium.Marker(
                            [row['latitude'], row['longitude']],
                            popup=row['name'],
                            tooltip=row['name']
                        ).add_to(m)

                folium_static(m, width=700, height=400)

    with col2:
        # Display filters summary
        st.subheader("🔍 Current Filters")
        st.write(f"State: **{selected_state if selected_state != 'All' else 'All States'}**")
        if search_query:
            st.write(f"Search: **{search_query}**")

    # Display destination cards
    st.subheader("🏞️ Destinations")

    if filtered_df.empty:
        st.warning("No destinations found matching your criteria. Try adjusting your filters.")
    else:
        for idx, row in filtered_df.iterrows():
            with st.expander(f"{row['name']}, {row['state']}", expanded=True):
                c1, c2 = st.columns([1, 2])

                with c1:
                    img = row.get('image_url') if pd.notnull(row.get('image_url')) and row.get('image_url') else None
                    if img:
                        st.image(img, use_column_width=True, caption=row['name'])
                    else:
                        st.text("No image available")

                with c2:
                    st.write(f"**State:** {row['state']}")
                    st.write(f"**Description:** {row['description']}")
                    if 'popular_attractions' in row and pd.notnull(row['popular_attractions']) and row['popular_attractions']:
                        st.write("**Popular Attractions:**")
                        attractions = [a.strip() for a in str(row['popular_attractions']).split(',') if a.strip()]
                        for attraction in attractions:
                            st.write(f"- {attraction}")

                    if 'latitude' in row and 'longitude' in row and pd.notnull(row['latitude']) and pd.notnull(row['longitude']):
                        st.button(
                            f"View on Map",
                            key=f"btn_{idx}",
                            on_click=None,
                            help=f"Show {row['name']} on the map"
                        )


if __name__ == "__main__":
    main()
