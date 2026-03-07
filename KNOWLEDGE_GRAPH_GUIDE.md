"""
Phase 6 — Concept Knowledge Graph Generation
=============================================

SETUP INSTRUCTIONS
------------------

1. Install dependencies:
   pip install spacy networkx pyvis
   python -m spacy download en_core_web_trf

2. Ensure you have transcripts from Phase 2:
   python scripts/run_phase2_asr.py

3. Run the knowledge graph pipeline:
   python scripts/build_concept_graph.py

4. View in browser:
   Open frontend/concept_graph.html


COMMAND-LINE OPTIONS
--------------------

python scripts/build_concept_graph.py [OPTIONS]

Options:
  --config PATH              Config file path (default: config/config.yaml)
  --transcripts-dir PATH     Transcripts directory (overrides config)
  --output-dir PATH          Output directory (overrides config)
  --limit N                  Process only first N transcripts
  --max-viz-nodes N          Max nodes in visualization (default: 100)
  --min-frequency N          Min concept frequency to keep (default: 2)
  --spacy-model NAME         spaCy model (default: en_core_web_trf)


EXAMPLES
--------

# Process all transcripts with default settings
python scripts/build_concept_graph.py

# Process first 10 transcripts only
python scripts/build_concept_graph.py --limit 10

# Generate larger visualization
python scripts/build_concept_graph.py --max-viz-nodes 200

# Use different spaCy model
python scripts/build_concept_graph.py --spacy-model en_core_web_sm

# Custom paths
python scripts/build_concept_graph.py \\
  --transcripts-dir data/transcripts \\
  --output-dir data/knowledge_graph


PROGRAMMATIC USAGE
------------------

from pathlib import Path
from src.knowledge_graph.concept_extractor import ConceptExtractor
from src.knowledge_graph.graph_builder import GraphBuilder

# Initialize
extractor = ConceptExtractor(model_name="en_core_web_trf")
builder = GraphBuilder()

# Extract concepts from text
text = "Neural networks use backpropagation for training."
concepts = extractor.extract_concepts(text)
print(f"Extracted: {concepts}")

# Extract concept pairs (relationships)
pairs = extractor.extract_concept_pairs(text)
print(f"Pairs: {pairs}")

# Build graph from transcripts
results = builder.build_from_transcripts(
    transcript_dir=Path("data/transcripts"),
    concept_extractor=extractor,
    limit=None,  # Process all
)

# Prune low-frequency concepts
builder.prune_graph(min_frequency=2, min_degree=1)

# Save graph files
builder.save_graph(Path("data/knowledge_graph/concept_graph"))

# Generate visualization
builder.visualize(
    output_path=Path("frontend/concept_graph.html"),
    title="Lecture Concept Graph",
    max_nodes=100,
)

# Get statistics
stats = builder.get_statistics()
print(f"Total concepts: {stats['num_concepts']}")
print(f"Relationships: {stats['num_relationships']}")
print(f"Top concepts: {stats['top_concepts'][:5]}")


FRONTEND INTEGRATION
--------------------

The Streamlit UI includes a button to explore the concept graph:

1. Start Streamlit:
   streamlit run frontend/streamlit_app.py

2. In the sidebar, click: "🔍 Explore Concept Graph"

3. The interactive visualization will open in your browser

4. Interact with the graph:
   - Hover over nodes: See concept details
   - Click and drag: Rearrange layout
   - Zoom: Mouse wheel
   - Navigate: Use on-screen controls


VISUALIZATION FEATURES
----------------------

Node Properties:
- Size: Proportional to concept frequency
- Color: Based on connectivity
  - Red: Highly connected (degree > 5)
  - Teal: Moderately connected (degree > 2)
  - Gray: Sparsely connected

Edge Properties:
- Width: Proportional to co-occurrence weight
- Direction: Shows relationship flow

Hover Information:
- Concept name
- Frequency count
- Number of connections
- Lecture references


OUTPUT FILES
------------

1. concept_graph.graphml
   - NetworkX graph in GraphML format
   - Preserves all node/edge attributes
   - Can be imported into other tools

2. concept_graph.json
   - JSON format with nodes and edges
   - Easy to parse and integrate

3. concept_graph.csv
   - Concept statistics table
   - Columns: concept, frequency, degree, in_degree, out_degree, num_lectures

4. frontend/concept_graph.html
   - Interactive PyVis visualization
   - Self-contained HTML file
   - Can be shared or embedded


CONFIGURATION
-------------

Edit config/config.yaml:

knowledge_graph:
  spacy_model: "en_core_web_trf"    # Transformer model for accuracy
  min_concept_length: 3              # Min characters
  max_concept_length: 50             # Max characters
  min_frequency: 2                   # Prune concepts below this
  min_degree: 1                      # Prune nodes with few connections
  max_distance: 10                   # Max token distance for relationships
  max_viz_nodes: 100                 # Limit visualization size


TROUBLESHOOTING
---------------

Issue: "Model not found" error
Solution: python -m spacy download en_core_web_trf

Issue: No transcripts found
Solution: Run Phase 2 first: python scripts/run_phase2_asr.py

Issue: Visualization too crowded
Solution: Reduce --max-viz-nodes or increase --min-frequency

Issue: Too few concepts
Solution: Lower --min-frequency threshold

Issue: Graph opens in wrong browser
Solution: Set your default browser in OS settings


PERFORMANCE NOTES
-----------------

- en_core_web_trf is accurate but slower
- Use en_core_web_sm for faster processing
- Process time: ~1-5 seconds per transcript
- Memory usage: ~1-2GB for transformer model
- Graph pruning significantly reduces visualization time


TESTING
-------

Run unit tests:
pytest tests/test_concept_extractor.py -v
pytest tests/test_graph_builder.py -v

Run all tests:
pytest tests/ -v --cov=src/knowledge_graph
"""