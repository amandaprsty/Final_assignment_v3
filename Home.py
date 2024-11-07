import streamlit as st
import json
import plotly.graph_objects as go
from datetime import datetime
import pandas as pd
import time  # Add missing time import
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.llms.openai import OpenAI
from llama_index.core.indices.prompt_helper import PromptHelper
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import download_loader
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext
from openai import OpenAI as OpenAIClient
import os
import tempfile
import chromadb

# Initialize session state variables
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'compliance_results' not in st.session_state:
    st.session_state.compliance_results = None
if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = None
if 'query_engine' not in st.session_state:
    st.session_state.query_engine = None
if 'llm' not in st.session_state:
    st.session_state.llm = None
if 'embed_model' not in st.session_state:
    st.session_state.embed_model = None
if 'prompt_helper' not in st.session_state:
    st.session_state.prompt_helper = None

# Load environment variables
load_dotenv()

# Define Australian Privacy Principles structure
APPS = {
    "APP1": {
        "title": "Open and transparent management of personal information",
        "requirements": [
            "privacy_management_framework",
            "security_system",
            "pia_implementation",
            "governance_mechanism",
            "staff_training",
            "proactive_review",
            "privacy_policy_updates"
        ],
        "details": {
            "privacy_management_framework": "Information cycle risk management",
            "security_system": "Personal information protection systems",
            "pia_implementation": "Privacy Impact Assessment for new projects",
            "governance_mechanism": "Regulatory compliance mechanisms",
            "staff_training": "Regular training and bulletins",
            "proactive_review": "Business operation adequacy audits",
            "privacy_policy_updates": "Industry-specific transparent policy"
        }
    },
    "APP2": {
        "title": "Anonymity and pseudonymity",
        "requirements": [
            "anonymity_option",
            "pseudonym_option"
        ],
        "details": {
            "anonymity_option": "Option to not identify themselves",
            "pseudonym_option": "Option to use a pseudonym"
        }
    },
    "APP3": {
        "title": "Collection of solicited personal information",
        "requirements": [
            "legitimate_collection",
            "objective_test",
            "sensitive_information_consent",
            "lawful_fair_collection"
        ],
        "details": {
            "legitimate_collection": "Reasonably necessary collection",
            "objective_test": "Reasonable person test",
            "sensitive_information_consent": "Consent for sensitive information",
            "lawful_fair_collection": "Lawful and fair collection means"
        }
    },
    "APP4": {
        "title": "Dealing with unsolicited personal information",
        "requirements": [
            "legitimate_determination",
            "destruction_deidentification"
        ],
        "details": {
            "legitimate_determination": "Legitimacy assessment process",
            "destruction_deidentification": "Process for destruction/de-identification"
        }
    },
    "APP5": {
        "title": "Notification of collection",
        "requirements": [
            "collection_notice",
            "overseas_disclosure_notice"
        ],
        "details": {
            "collection_notice": "Reasonable steps for notice",
            "overseas_disclosure_notice": "Overseas transfer notification"
        }
    },
    "APP6": {
        "title": "Use or disclosure of personal information",
        "requirements": [
            "purpose_alignment",
            "consent_requirements"
        ],
        "details": {
            "purpose_alignment": "Alignment with collection purpose",
            "consent_requirements": "Additional consent process"
        }
    },
    "APP7": {
        "title": "Direct marketing",
        "requirements": [
            "marketing_consent",
            "opt_out_mechanism",
            "information_source_disclosure"
        ],
        "details": {
            "marketing_consent": "Consent for direct marketing",
            "opt_out_mechanism": "Opt-out process",
            "information_source_disclosure": "Information source disclosure"
        }
    },
    "APP8": {
        "title": "Cross-border disclosure",
        "requirements": [
            "overseas_compliance",
            "adequacy_assessment",
            "express_consent",
            "cloud_storage_handling",
            "jurisdictional_considerations"
        ],
        "details": {
            "overseas_compliance": "Overseas recipient compliance",
            "adequacy_assessment": "Privacy protection adequacy",
            "express_consent": "Express consent for transfers",
            "cloud_storage_handling": "Cloud storage compliance",
            "jurisdictional_considerations": "Jurisdictional requirements"
        }
    },
    "APP9": {
        "title": "Government identifiers",
        "requirements": [
            "identifier_handling"
        ],
        "details": {
            "identifier_handling": "Government identifier management"
        }
    },
    "APP10": {
        "title": "Quality of personal information",
        "requirements": [
            "data_quality_maintenance"
        ],
        "details": {
            "data_quality_maintenance": "Data accuracy and updates"
        }
    },
    "APP11": {
        "title": "Security of personal information",
        "requirements": [
            "security_measures",
            "third_party_destruction"
        ],
        "details": {
            "security_measures": "Protection against misuse/interference",
            "third_party_destruction": "Third-party destruction verification"
        }
    },
    "APP12": {
        "title": "Access to personal information",
        "requirements": [
            "access_process",
            "reason_prohibition"
        ],
        "details": {
            "access_process": "Access provision process",
            "reason_prohibition": "No reason requirement policy"
        }
    },
    "APP13": {
        "title": "Correction of personal information",
        "requirements": [
            "correction_process"
        ],
        "details": {
            "correction_process": "Information correction process"
        }
    }
}

# Add new function for PDF report generation
def generate_pdf_report(results):
    """Generate a PDF compliance report"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    import io
    
    # Create buffer for PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30
    )
    story.append(Paragraph("Privacy Policy Compliance Report", title_style))
    story.append(Spacer(1, 12))
    
    # Summary section
    story.append(Paragraph("Executive Summary", styles['Heading2']))
    
    # Calculate overall compliance
    overall_score = sum(app_data['compliance_score'] for app_data in results.values()) / len(results)
    summary_data = [
        ["Overall Compliance Score", f"{overall_score:.1f}%"],
        ["Assessment Date", datetime.now().strftime("%Y-%m-%d")],
    ]
    
    summary_table = Table(summary_data)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))
    
    # Detailed analysis for each APP
    story.append(Paragraph("Detailed Analysis", styles['Heading2']))
    
    for app, data in results.items():
        # APP header
        story.append(Paragraph(f"{app}: {data['title']}", styles['Heading3']))
        story.append(Paragraph(f"Compliance Score: {data['compliance_score']:.1f}%", styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Requirements analysis
        for req, results in data['detailed_results'].items():
            status = "✓" if results['compliance_status'] else "✗"
            story.append(Paragraph(f"{status} {req}", styles['Normal']))
            story.append(Paragraph(f"Evidence: {results['evidence']}", styles['Normal']))
            
            if results['recommendations']:
                story.append(Paragraph("Recommendations:", styles['Normal']))
                for rec in results['recommendations']:
                    story.append(Paragraph(f"• {rec}", styles['Normal']))
            
            story.append(Spacer(1, 12))
        
        story.append(Spacer(1, 20))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# Update the main function to include PDF report generation
def main():
    # ... [previous code remains the same until the report generation section]
    
    # Modify the report generation section
    if st.session_state.analysis_complete and st.session_state.compliance_results:
        st.markdown("## Download Reports")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Download PDF Report"):
                pdf_buffer = generate_pdf_report(st.session_state.compliance_results)
                st.download_button(
                    label="Download PDF",
                    data=pdf_buffer,
                    file_name="privacy_compliance_report.pdf",
                    mime="application/pdf"
                )
        
        with col2:
            if st.button("Download JSON Report"):
                report = generate_report(st.session_state.compliance_results)
                st.download_button(
                    label="Download JSON",
                    data=json.dumps(report, indent=2),
                    file_name="privacy_compliance_report.json",
                    mime="application/json"
                )

def setup_openai(api_key):
    """Setup OpenAI client with provided API key"""
    if not api_key:
        raise ValueError("OpenAI API key is required")
    return OpenAIClient(api_key=api_key)

def initialize_vector_store():
    """Initialize ChromaDB and create collection if it doesn't exist"""
    try:
        # Ensure the directory exists
        os.makedirs("./chroma_db", exist_ok=True)
        
        # Initialize the persistent client
        chroma_client = chromadb.PersistentClient(path="./chroma_db")
        
        # Create or get collection
        try:
            chroma_collection = chroma_client.get_or_create_collection(
                name="privacy_docs",
                metadata={"description": "Privacy policy documents collection"}
            )
        except Exception as e:
            # If there's an error with existing collection, recreate it
            try:
                chroma_client.delete_collection("privacy_docs")
            except:
                pass
            chroma_collection = chroma_client.create_collection(
                name="privacy_docs",
                metadata={"description": "Privacy policy documents collection"}
            )
            
        return chroma_collection
    
    except Exception as e:
        st.error(f"Error initializing vector store: {str(e)}")
        raise

# Modify the setup_llama_components function
def setup_llama_components(api_key):
    """Setup LlamaIndex components with provided API key"""
    if not api_key:
        raise ValueError("OpenAI API key is required")
    
    os.environ["OPENAI_API_KEY"] = api_key
    # Change to gpt-3.5-turbo instead of gpt-4
    llm = OpenAI(model="gpt-3.5-turbo", temperature=0.1)
    embed_model = OpenAIEmbedding()
    prompt_helper = PromptHelper(
        context_window=4096,
        num_output=512,
        chunk_overlap_ratio=0.1,
        chunk_size_limit=None
    )
    return llm, embed_model, prompt_helper

# Improve the analyze_app_compliance function with better error handling
def analyze_app_compliance(query_engine, app_number, requirements):
    """
    Analyze compliance for a specific APP and its requirements with improved error handling
    """
    results = {}
    app_title = APPS[f"APP{app_number}"]["title"]
    
    for requirement in requirements:
        try:
            # Create analysis prompt with more specific guidance
            prompt = f"""
            Analyze the provided privacy policy document for compliance with Australian Privacy Principle (APP) {app_number}: {app_title}
            Specifically evaluate the requirement: {requirement}
            
            Focus on these aspects:
            1. Does the document explicitly address this requirement?
            2. Are there specific procedures or practices described?
            3. Is the implementation clear and adequate?
            
            Provide your analysis in this exact JSON format:
            {{
                "compliance_status": true/false,
                "evidence": "Quote specific relevant sections from the document. If none found, state 'No relevant sections found.'",
                "recommendations": ["List specific, actionable recommendations"],
                "confidence_score": "A number between 0-100"
            }}
            
            Base your assessment strictly on the document content.
            """
            
            # Query the document with timeout and retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = query_engine.query(prompt)
                    requirement_result = parse_analysis_response(response.response)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        requirement_result = {
                            "compliance_status": False,
                            "evidence": f"Analysis incomplete: {str(e)}",
                            "recommendations": ["Manual review required - automated analysis failed"],
                            "confidence_score": 0
                        }
                    continue
            
            results[requirement] = requirement_result
            
        except Exception as e:
            results[requirement] = {
                "compliance_status": False,
                "evidence": f"Analysis error: {str(e)}",
                "recommendations": ["Manual review required - system error occurred"],
                "confidence_score": 0
            }
            
        # Add small delay between requests to avoid rate limiting
        time.sleep(1)
    
    return results

# Improve the parse_analysis_response function
def parse_analysis_response(response_text):
    """Parse and validate the analysis response with better error handling"""
    try:
        # Clean the response text if needed
        if isinstance(response_text, str):
            # Remove any leading/trailing whitespace or special characters
            cleaned_text = response_text.strip()
            # Try to find JSON content if wrapped in other text
            start_idx = cleaned_text.find('{')
            end_idx = cleaned_text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                cleaned_text = cleaned_text[start_idx:end_idx + 1]
            result = json.loads(cleaned_text)
        else:
            result = response_text
        
        # Validate and normalize the response
        return {
            "compliance_status": bool(result.get('compliance_status', False)),
            "evidence": str(result.get('evidence', "No evidence provided")),
            "recommendations": list(result.get('recommendations', ["No specific recommendations provided"])),
            "confidence_score": int(float(result.get('confidence_score', 0)))
        }
    except json.JSONDecodeError:
        # Handle case where response isn't valid JSON
        return {
            "compliance_status": False,
            "evidence": "Error: Could not parse analysis response",
            "recommendations": ["Manual review required - response format error"],
            "confidence_score": 0
        }
    except Exception as e:
        return {
            "compliance_status": False,
            "evidence": f"Error parsing analysis: {str(e)}",
            "recommendations": ["Manual review required - parsing error"],
            "confidence_score": 0
        }

# Add a new function to validate document content
def validate_document_content(documents):
    """Validate that the document contains analyzable content"""
    if not documents:
        raise ValueError("No content found in the document")
    
    total_content = " ".join(doc.text for doc in documents)
    if len(total_content.strip()) < 50:  # Arbitrary minimum length
        raise ValueError("Document contains insufficient content for analysis")
    
    return True

# Update the main function's document processing section
def process_document(uploaded_file, temp_file_path):
    """Process the uploaded document with validation"""
    try:
        # Initialize vector store
        chroma_collection = initialize_vector_store()
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # Load document based on type
        if uploaded_file.type == "application/pdf":
            PDFReader = download_loader("PDFReader")
            loader = PDFReader()
            documents = loader.load_data(file=temp_file_path)
        else:
            documents = SimpleDirectoryReader(input_files=[temp_file_path]).load_data()

        # Validate document content
        if validate_document_content(documents):
            index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context,
                embed_model=st.session_state.embed_model,  # Use session state
                prompt_helper=st.session_state.prompt_helper  # Use session state
            )
            return index.as_query_engine(llm=st.session_state.llm)  # Use session state
        
    except Exception as e:
        st.error(f"Error processing document: {str(e)}")
        return None

def calculate_app_score(results):
    """Calculate overall compliance score for an APP"""
    if not results:
        return 0
    
    total_requirements = len(results)
    compliant_requirements = sum(1 for r in results.values() if r['compliance_status'])
    confidence_sum = sum(r.get('confidence_score', 0) for r in results.values())
    
    # Weight the score by both compliance and confidence
    compliance_score = (compliant_requirements / total_requirements) * 100
    confidence_factor = (confidence_sum / (total_requirements * 100))
    
    return compliance_score * confidence_factor

def create_compliance_visualization(results):
    """Create a Plotly visualization of compliance results"""
    apps = list(results.keys())
    compliance_scores = []
    confidence_scores = []
    
    for app in apps:
        app_results = results[app]['detailed_results']
        compliance_scores.append(calculate_app_score(app_results))
        confidence_scores.append(
            sum(r.get('confidence_score', 0) for r in app_results.values()) / len(app_results)
        )
    
    # Create compliance score bar chart
    fig = go.Figure(data=[
        go.Bar(
            name='Compliance Score',
            x=apps,
            y=compliance_scores,
            marker_color=['green' if score >= 75 else 'yellow' if score >= 50 else 'red' 
                         for score in compliance_scores]
        ),
        go.Scatter(
            name='Confidence Level',
            x=apps,
            y=confidence_scores,
            mode='lines+markers',
            line=dict(color='blue'),
            yaxis='y2'
        )
    ])
    
    # Update layout for dual axis
    fig.update_layout(
        title="Privacy Principles Compliance Overview",
        xaxis_title="Australian Privacy Principles",
        yaxis_title="Compliance Score (%)",
        yaxis2=dict(
            title="Confidence Score (%)",
            overlaying='y',
            side='right'
        ),
        yaxis=dict(range=[0, 100]),
        yaxis2_range=[0, 100],
        barmode='group',
        legend=dict(
            x=1.1,
            y=1,
            xanchor='left'
        )
    )
    
    return fig

def generate_report(results):
    """Generate a comprehensive compliance report"""
    timestamp = datetime.now().isoformat()
    
    report = {
        "timestamp": timestamp,
        "summary": {
            "overall_compliance_score": 0,
            "average_confidence_score": 0,
            "high_priority_recommendations": [],
            "compliance_by_app": {}
        },
        "detailed_results": results
    }
    
    # Calculate overall scores
    total_score = 0
    total_confidence = 0
    num_apps = len(results)
    
    for app, data in results.items():
        app_results = data['detailed_results']
        app_score = calculate_app_score(app_results)
        app_confidence = sum(r.get('confidence_score', 0) for r in app_results.values()) / len(app_results)
        
        report["summary"]["compliance_by_app"][app] = {
            "score": app_score,
            "confidence": app_confidence
        }
        
        total_score += app_score
        total_confidence += app_confidence
        
        # Collect high-priority recommendations for low-scoring areas
        if app_score < 75:
            for rec in data['recommendations']:
                report["summary"]["high_priority_recommendations"].append(f"{app}: {rec}")
    
    report["summary"]["overall_compliance_score"] = total_score / num_apps
    report["summary"]["average_confidence_score"] = total_confidence / num_apps
    
    return report

# ... [Previous analyze_app_compliance, create_compliance_visualization, and generate_report functions remain the same]

# Update the main function
def main():
    st.set_page_config(page_title="PrivacyLens: APP Compliance Analyzer", layout="wide")
    st.title("PrivacyLens: Australian Privacy Principles Compliance Analyzer")

    # API Key Input in Sidebar
    with st.sidebar:
        st.title("Configuration")
        api_key_input = st.text_input("Enter OpenAI API Key:", type="password", key="api_key_input")
        if api_key_input:
            st.session_state.openai_api_key = api_key_input
            st.success("API Key set successfully!")
        
        if not st.session_state.openai_api_key:
            st.error("Please enter your OpenAI API key to continue.")
            st.stop()
    
    try:
        # Initialize components only if API key is available
        if st.session_state.openai_api_key:
            openai_client = setup_openai(st.session_state.openai_api_key)
            chroma_collection = initialize_vector_store()
            llm, embed_model, prompt_helper = setup_llama_components(st.session_state.openai_api_key)
            
            # File Upload Section
            st.sidebar.markdown("### Upload Privacy Policy Document")
            uploaded_file = st.sidebar.file_uploader("Choose a file", type=["txt", "pdf"])
            
            if uploaded_file:
                    with st.spinner("Processing document..."):
                        try:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as temp_file:
                                temp_file.write(uploaded_file.getvalue())
                                temp_file_path = temp_file.name

                            query_engine = process_document(uploaded_file, temp_file_path)
                
                            if query_engine:
                                st.success("Document processed successfully!")
                                st.session_state.query_engine = query_engine
                            else:
                                st.error("Failed to process document")
    
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                        finally:
                            if os.path.exists(temp_file_path):
                                os.unlink(temp_file_path)
        
                        if st.sidebar.button("Run Compliance Analysis"):
                            results = {}
                            progress_bar = st.progress(0)
                            
                            for i, (app, details) in enumerate(APPS.items()):
                                with st.spinner(f"Analyzing {app}..."):
                                    app_results = analyze_app_compliance(
                                        query_engine,
                                        app.replace("APP", ""),
                                        details["requirements"]
                                    )
                                    
                                    # Calculate compliance score
                                    compliance_count = sum(1 for req in app_results.values() 
                                                        if req["compliance_status"])
                                    compliance_score = (compliance_count / len(details["requirements"])) * 100
                                    
                                    results[app] = {
                                        "title": details["title"],
                                        "compliance_score": compliance_score,
                                        "detailed_results": app_results,
                                        "recommendations": [rec for req in app_results.values() 
                                                          for rec in req["recommendations"]]
                                    }
                                    
                                    progress_bar.progress((i + 1) / len(APPS))
                            
                            st.session_state.compliance_results = results
                            st.session_state.analysis_complete = True
            
            # Display results if analysis is complete
            if st.session_state.analysis_complete and st.session_state.compliance_results:
                # Display compliance visualization
                st.plotly_chart(create_compliance_visualization(st.session_state.compliance_results))
                
                # Detailed results
                st.markdown("## Detailed Compliance Analysis")
                for app, data in st.session_state.compliance_results.items():
                    with st.expander(f"{app}: {data['title']} - {data['compliance_score']:.1f}%"):
                        st.markdown("### Detailed Requirements Analysis")
                        for req, results in data["detailed_results"].items():
                            status_icon = "✅" if results["compliance_status"] else "❌"
                            st.markdown(f"**{req}** {status_icon}")
                            st.markdown(f"Evidence: {results['evidence']}")
                            if results["recommendations"]:
                                st.markdown("Recommendations:")
                                for rec in results["recommendations"]:
                                    st.markdown(f"- {rec}")
                
                # Download report
                if st.button("Generate Compliance Report"):
                    report = generate_report(st.session_state.compliance_results)
                    st.download_button(
                        label="Download Report",
                        data=json.dumps(report, indent=2),
                        file_name="privacy_compliance_report.json",
                        mime="application/json"
                    )
                    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()