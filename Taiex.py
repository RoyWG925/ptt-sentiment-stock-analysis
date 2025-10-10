import networkx as nx
from pyvis.network import Network

# 建立有向圖
G = nx.DiGraph()

# 節點類型標籤
G.add_node("Event: Tariff Announce", type="Event")
G.add_node("Post: Article123", type="Post")
G.add_node("Comment: Push456", type="Comment")
G.add_node("MarketIndex: 2025-04-07", type="MarketIndex")

# 邊：定義關係
G.add_edge("Post: Article123", "Event: Tariff Announce", relation="belongs_to")
G.add_edge("Comment: Push456", "Post: Article123", relation="comments_on")
G.add_edge("Post: Article123", "MarketIndex: 2025-04-07", relation="date_associated")

# 視覺化，產生互動網頁
net = Network(notebook=True)
net.from_nx(G)

# 節點顏色根據類型
for node in net.nodes:
    if node['id'].startswith("Event"):
        node['color'] = 'orange'
    elif node['id'].startswith("Post"):
        node['color'] = 'lightblue'
    elif node['id'].startswith("Comment"):
        node['color'] = 'lightgreen'
    elif node['id'].startswith("MarketIndex"):
        node['color'] = 'pink'

net.show("ontology_graph.html")
