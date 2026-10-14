import streamlit as st
import pymongo
from pymongo import MongoClient
import cloudinary
from cloudinary import CloudinaryImage
import cloudinary.uploader
import cloudinary.api
import os

# -----------------------------------------------------------------------------
# 1. SETUP / CONFIGURATION DICTIONARY
# -----------------------------------------------------------------------------
CONFIG = {
    "MONGO_URI": os.environ.get("MONGO_URI", "mongodb://localhost:27017/"),
    "DB_NAME": os.environ.get("DB_NAME", "image_gallery"),
    "COLLECTION_NAME": os.environ.get("COLLECTION_NAME", "metadata"),
    
    "CLOUDINARY_CLOUD_NAME": os.environ.get("CLOUDINARY_CLOUD_NAME", "your_cloud_name"),
    "CLOUDINARY_API_KEY": os.environ.get("CLOUDINARY_API_KEY", "your_api_key"),
    "CLOUDINARY_API_SECRET": os.environ.get("CLOUDINARY_API_SECRET", "your_api_secret"),
}

if "MONGO_URI" in st.secrets:
    CONFIG.update(st.secrets)

# Initialize Cloudinary
if CONFIG["CLOUDINARY_CLOUD_NAME"] and CONFIG["CLOUDINARY_API_KEY"] and CONFIG["CLOUDINARY_API_SECRET"]:
    cloudinary.config(
        cloud_name=CONFIG["CLOUDINARY_CLOUD_NAME"],
        api_key=CONFIG["CLOUDINARY_API_KEY"],
        api_secret=CONFIG["CLOUDINARY_API_SECRET"],
        secure=True
    )

# Establish MongoDB Connection
@st.cache_resource
def init_mongo(uri):
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        client.server_info()
        return client
    except Exception as e:
        st.error(f"❌ MongoDB Connection failed: {e}")
        return None

client = init_mongo(CONFIG["MONGO_URI"])
collection = client[CONFIG["DB_NAME"]][CONFIG["COLLECTION_NAME"]] if client else None

# -----------------------------------------------------------------------------
# 2. MAIN APPLICATION INTERFACE
# -----------------------------------------------------------------------------
st.title("🤖 AI-Driven Cloudinary & MongoDB Studio")
st.markdown("Select an image from **MongoDB** and use **Natural Language AI Queries** to modify it on the fly.")

tabs = st.tabs(["✨ AI Workspace", "📤 Upload New Asset", "📋 View Database Records"])

# -----------------------------------------------------------------------------
# TAB 1: AI WORKSPACE & TEXT QUERY PARSING
# -----------------------------------------------------------------------------
with tabs[0]:
    st.subheader("Modify Asset via AI Natural Language")
    
    if collection is not None:
        try:
            records = list(collection.find({}, {"public_id": 1, "title": 1, "_id": 0}))
            
            if records:
                asset_options = {f"{r.get('title', 'Untitled')} ({r['public_id']})": r['public_id'] for r in records}
                selected_label = st.selectbox("Select an Image Asset from MongoDB:", list(asset_options.keys()))
                selected_public_id = asset_options[selected_label]
                
                img_metadata = collection.find_one({"public_id": selected_public_id})
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.markdown("### 💬 Describe your AI Modification")
                    
                    # 1. Choose the type of AI operation
                    ai_action = st.radio(
                        "Select AI Mode:",
                        ["Generative Recolor / Restyle", "Generative Replace Object", "Generative Remove Background/Object"]
                    )
                    
                    # 2. Capture the user's natural language query as a pure string
                    user_query = st.text_input(
                        "Enter your string prompt:", 
                        placeholder="e.g., 'change background to a neon cyberpunk city' or 'recolor coat to deep red'"
                    )
                    
                    # Build Cloudinary transformation array dynamically based on the AI string prompt
                    transformation_list = []
                    
                    if user_query:
                        if ai_action == "Generative Recolor / Restyle":
                            # Syntax syntax for recoloring via string inputs: e.g., "gen_recolor:prompt_recolor coat to blue"
                            transformation_list.append({"effect": f"gen_recolor:prompt_{user_query}"})
                            
                        elif ai_action == "Generative Replace Object":
                            # For replacing elements, you can prompt things like "from_dog;to_cat"
                            transformation_list.append({"effect": f"gen_replace:prompt_{user_query}"})
                            
                        elif ai_action == "Generative Remove Background/Object":
                            transformation_list.append({"effect": f"gen_remove:prompt_{user_query}"})
                    else:
                        st.info("💡 Type an AI modification prompt above to trigger real-time image updates.")
                        
                with col2:
                    st.markdown("### 🌅 Live AI Output Preview")
                    try:
                        transformed_image = CloudinaryImage(selected_public_id)
                        
                        # Generate the transformation URL using our AI string injection array
                        if transformation_list:
                            transformed_url = transformed_image.build_url(transformation=transformation_list)
                        else:
                            # Fallback to standard URL if no prompt text is supplied
                            transformed_url = transformed_image.build_url()
                        
                        st.image(transformed_url, caption="AI Transformation Pipeline Result", use_container_width=True)
                        st.code(transformed_url, language="text")
                    except Exception as cloud_err:
                        st.error(f"Cloudinary rendering issue: {cloud_err}")
                        
                with st.expander("🗄️ Stored MongoDB Metadata Document"):
                    st.json(str(img_metadata))
            else:
                st.warning("No records found in MongoDB. Upload an asset to get started.")
        except Exception as query_err:
            st.error(f"Error querying records: {query_err}")
    else:
        st.error("Database connection missing.")

# Keep Tab 2 & 3 running exactly the same way to let users upload assets seamlessly...
with tabs[1]:
    st.subheader("Upload Image to Cloudinary & Index in MongoDB")
    upload_title = st.text_input("Asset Title Reference", placeholder="e.g., Car Photo")
    uploaded_file = st.file_uploader("Choose an image file...", type=["jpg", "jpeg", "png", "webp"])
    
    if st.button("🚀 Upload and Index Asset"):
        if collection is not None and upload_title and uploaded_file:
            with st.spinner("Uploading..."):
                try:
                    upload_result = cloudinary.uploader.upload(uploaded_file, folder=f"{CONFIG['DB_NAME']}/uploads")
                    metadata_payload = {
                        "title": upload_title,
                        "public_id": upload_result.get("public_id"),
                        "secure_url": upload_result.get("secure_url"),
                    }
                    collection.insert_one(metadata_payload)
                    st.success("🎉 Asset uploaded and metadata index generated!")
                except Exception as upload_err:
                    st.error(f"Upload failed: {upload_err}")

with tabs[2]:
    st.subheader("📋 MongoDB Metadata Records Index")
    if collection is not None:
        try:
            for doc in list(collection.find({})):
                with st.container(border=True):
                    st.markdown(f"#### 📄 {doc.get('title', 'Untitled Asset')}")
                    st.text(f"Public ID: {doc.get('public_id')}")
        except Exception as err:
            st.error(f"Failed to fetch records: {err}")
