#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <sstream>
#include <algorithm>

// Define a struct for Node representation in C++ using memory-efficient types
struct Node {
    std::string id;
    std::string label;
    bool is_defined;
    bool is_class;
    int lineno;
    std::string filepath;
    int loc;
    int complexity;
    bool is_unused;
    std::string module_prefix;
    std::vector<std::string> decorators;
};

struct Edge {
    std::string from_id;
    std::string to_id;
    int value;
    std::string type;
};

// Main Graph Database Class
class CallGraph {
public:
    std::unordered_map<std::string, Node> nodes;
    std::vector<Edge> edges;
    
    // We also store Keras nodes and edges in a separate list to mirror model_graph
    std::vector<std::string> model_node_ids; 
    std::unordered_map<std::string, std::string> model_node_labels;
    std::unordered_map<std::string, std::string> model_node_layer_types;
    std::unordered_map<std::string, std::string> model_node_shapes;
    std::unordered_map<std::string, std::string> model_node_params;
    std::unordered_map<std::string, std::string> model_node_filepaths;
    std::unordered_map<std::string, int> model_node_linenos;
    std::unordered_map<std::string, std::string> model_node_namespaces;

    std::vector<Edge> model_edges;

    void add_node(const char* id, const char* label, bool is_defined, bool is_class, int lineno, 
                  const char* filepath, int loc, int complexity, bool is_unused, 
                  const char* module_prefix, const char* decorators_csv) {
        std::string s_id(id);
        Node& n = nodes[s_id];
        n.id = s_id;
        n.label = label ? label : "";
        n.is_defined = is_defined;
        n.is_class = is_class;
        n.lineno = lineno;
        n.filepath = filepath ? filepath : "";
        n.loc = loc;
        n.complexity = complexity;
        n.is_unused = is_unused;
        n.module_prefix = module_prefix ? module_prefix : "";
        
        n.decorators.clear();
        if (decorators_csv && *decorators_csv) {
            std::stringstream ss(decorators_csv);
            std::string item;
            while (std::getline(ss, item, ',')) {
                if (!item.empty()) {
                    n.decorators.push_back(item);
                }
            }
        }
    }

    void add_edge(const char* from_id, const char* to_id, int value, const char* type) {
        Edge e;
        e.from_id = from_id ? from_id : "";
        e.to_id = to_id ? to_id : "";
        e.value = value;
        e.type = type ? type : "call";
        edges.push_back(e);
    }

    void add_model_node(const char* id, const char* label, const char* layer_type, const char* shape,
                        const char* params, const char* filepath, int lineno, const char* namespace_val) {
        std::string s_id(id);
        if (std::find(model_node_ids.begin(), model_node_ids.end(), s_id) == model_node_ids.end()) {
            model_node_ids.push_back(s_id);
        }
        model_node_labels[s_id] = label ? label : "";
        model_node_layer_types[s_id] = layer_type ? layer_type : "";
        model_node_shapes[s_id] = shape ? shape : "";
        model_node_params[s_id] = params ? params : "";
        model_node_filepaths[s_id] = filepath ? filepath : "";
        model_node_linenos[s_id] = lineno;
        model_node_namespaces[s_id] = namespace_val ? namespace_val : "";
    }

    void add_model_edge(const char* from_id, const char* to_id, const char* tensor_shape) {
        Edge e;
        e.from_id = from_id ? from_id : "";
        e.to_id = to_id ? to_id : "";
        e.value = 1;
        e.type = tensor_shape ? tensor_shape : "";
        model_edges.push_back(e);
    }

    std::string to_json() {
        std::stringstream ss;
        ss << "{";
        
        // 1. Nodes
        ss << "\"nodes\":[";
        bool first_node = true;
        for (auto const& [key, n] : nodes) {
            if (!first_node) ss << ",";
            first_node = false;
            
            ss << "{";
            ss << "\"id\":\"" << escape_json(n.id) << "\",";
            ss << "\"label\":\"" << escape_json(n.label) << "\",";
            ss << "\"is_defined\":" << (n.is_defined ? "true" : "false") << ",";
            ss << "\"is_class\":" << (n.is_class ? "true" : "false") << ",";
            
            if (n.lineno >= 0) ss << "\"lineno\":" << n.lineno << ",";
            else ss << "\"lineno\":null,";
            
            ss << "\"filepath\":" << (n.filepath.empty() ? "null" : "\"" + escape_json(n.filepath) + "\"") << ",";
            
            if (n.loc >= 0) ss << "\"loc\":" << n.loc << ",";
            else ss << "\"loc\":null,";
            
            if (n.complexity >= 0) ss << "\"complexity\":" << n.complexity << ",";
            else ss << "\"complexity\":null,";
            
            ss << "\"is_unused\":" << (n.is_unused ? "true" : "false") << ",";
            ss << "\"module_prefix\":" << (n.module_prefix.empty() ? "null" : "\"" + escape_json(n.module_prefix) + "\"") << ",";
            
            ss << "\"decorators\":[";
            for (size_t i = 0; i < n.decorators.size(); ++i) {
                if (i > 0) ss << ",";
                ss << "\"" << escape_json(n.decorators[i]) << "\"";
            }
            ss << "]";
            ss << "}";
        }
        ss << "],";

        // 2. Edges
        ss << "\"edges\":[";
        for (size_t i = 0; i < edges.size(); ++i) {
            if (i > 0) ss << ",";
            ss << "{";
            ss << "\"from\":\"" << escape_json(edges[i].from_id) << "\",";
            ss << "\"to\":\"" << escape_json(edges[i].to_id) << "\",";
            ss << "\"value\":" << edges[i].value << ",";
            ss << "\"type\":\"" << escape_json(edges[i].type) << "\"";
            ss << "}";
        }
        ss << "],";

        // 3. Model Graph
        ss << "\"model_graph\":{";
        ss << "\"nodes\":[";
        for (size_t i = 0; i < model_node_ids.size(); ++i) {
            if (i > 0) ss << ",";
            std::string s_id = model_node_ids[i];
            ss << "{";
            ss << "\"id\":\"" << escape_json(s_id) << "\",";
            ss << "\"label\":\"" << escape_json(model_node_labels[s_id]) << "\",";
            ss << "\"type\":\"" << escape_json(model_node_layer_types[s_id]) << "\",";
            ss << "\"layer_type\":\"" << escape_json(model_node_layer_types[s_id]) << "\",";
            ss << "\"output_shape\":\"" << escape_json(model_node_shapes[s_id]) << "\",";
            ss << "\"parameters\":\"" << escape_json(model_node_params[s_id]) << "\",";
            ss << "\"filepath\":\"" << escape_json(model_node_filepaths[s_id]) << "\",";
            ss << "\"lineno\":" << model_node_linenos[s_id] << ",";
            ss << "\"namespace\":\"" << escape_json(model_node_namespaces[s_id]) << "\"";
            ss << "}";
        }
        ss << "],";
        ss << "\"edges\":[";
        for (size_t i = 0; i < model_edges.size(); ++i) {
            if (i > 0) ss << ",";
            ss << "{";
            ss << "\"from\":\"" << escape_json(model_edges[i].from_id) << "\",";
            ss << "\"to\":\"" << escape_json(model_edges[i].to_id) << "\",";
            ss << "\"tensor_shape\":\"" << escape_json(model_edges[i].type) << "\"";
            ss << "}";
        }
        ss << "]";
        ss << "}";

        ss << "}";
        return ss.str();
    }

private:
    std::string escape_json(const std::string& s) {
        std::stringstream ss;
        for (char c : s) {
            if (c == '"') ss << "\\\"";
            else if (c == '\\') ss << "\\\\";
            else if (c == '\n') ss << "\\n";
            else if (c == '\r') ss << "\\r";
            else if (c == '\t') ss << "\\t";
            else if (c == '\b') ss << "\\b";
            else if (c == '\f') ss << "\\f";
            else if ((unsigned char)c < 32) {
                // Ignore non-printable control chars
            } else {
                ss << c;
            }
        }
        return ss.str();
    }
};

// C Interface for ctypes binding
extern "C" {
    __declspec(dllexport) void* create_graph() {
        return new CallGraph();
    }

    __declspec(dllexport) void free_graph(void* graph) {
        delete static_cast<CallGraph*>(graph);
    }

    __declspec(dllexport) void add_node(void* graph, const char* id, const char* label, bool is_defined, 
                                        bool is_class, int lineno, const char* filepath, int loc, 
                                        int complexity, bool is_unused, const char* module_prefix, 
                                        const char* decorators_csv) {
        static_cast<CallGraph*>(graph)->add_node(id, label, is_defined, is_class, lineno, 
                                                 filepath, loc, complexity, is_unused, 
                                                 module_prefix, decorators_csv);
    }

    __declspec(dllexport) void add_edge(void* graph, const char* from_id, const char* to_id, int value, const char* type) {
        static_cast<CallGraph*>(graph)->add_edge(from_id, to_id, value, type);
    }

    __declspec(dllexport) void add_model_node(void* graph, const char* id, const char* label, const char* layer_type, 
                                              const char* shape, const char* params, const char* filepath, 
                                              int lineno, const char* namespace_val) {
        static_cast<CallGraph*>(graph)->add_model_node(id, label, layer_type, shape, params, filepath, lineno, namespace_val);
    }

    __declspec(dllexport) void add_model_edge(void* graph, const char* from_id, const char* to_id, const char* tensor_shape) {
        static_cast<CallGraph*>(graph)->add_model_edge(from_id, to_id, tensor_shape);
    }

    __declspec(dllexport) const char* get_graph_json(void* graph) {
        static std::string result_cache; 
        result_cache = static_cast<CallGraph*>(graph)->to_json();
        return result_cache.c_str();
    }
}
