// simple.frag
// Basit mod fragment shader'ı.
// MRT: renk (location 0) + pick ID (location 1).

#version 460 core

// ---- Vertex'ten gelen ----
in vec3      VertexColor;
flat in uint PickID;

// ---- MRT output ----
layout(location = 0) out vec4 FragColor;
layout(location = 1) out uint FragID;

// ---- Uniform'lar ----
uniform bool  useVertexColor;
uniform vec3  objectColor;
uniform float alpha;

void main() {
    vec3 color = useVertexColor ? VertexColor : objectColor;

    FragColor = vec4(color, alpha);
    FragID    = PickID;
}