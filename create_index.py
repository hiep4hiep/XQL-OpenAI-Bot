#This only needs to be executed whenever instruction_query_pairs.csv is updated
#This generates the embedding results and saves to instruction_query_pairs_embeddings.csv which will be used by the bot

import pandas as pd
import openai
from openai.embeddings_utils import get_embedding
import pandas as pd
from dotenv import load_dotenv
import os


load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
EMBEDDING_MODEL_NAME = "curie"

openai.api_key = OPENAI_API_KEY

input_datapath = './instruction_query_pairs.csv'
df = pd.read_csv(input_datapath, header=0)

df['Similarity'] = df.Instruction.apply(lambda x: get_embedding(x, engine=f"text-search-{EMBEDDING_MODEL_NAME}-doc-001"))
#df['ada_search'] = df.combined.apply(lambda x: get_embedding(x, engine='text-embedding-ada-002'))
df.to_csv('./instruction_query_pairs_embeddings.csv', index=False)