// simple.vert
// Basit mod vertex shader'ı (Frame, Area, Link, Node, Restraint).
// MRT: renk (location 0) + pick ID (location 1).

#version 460 core

// ---- Vertex input ----
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aColor;
layout(location = 3) in uint aPickID;

// ---- Fragment'e aktarılan ----
out vec3      VertexColor;
flat out uint PickID;

// ---- Uniform ----
uniform mat4 mvp;

void main() {
    gl_Position = mvp * vec4(aPos, 1.0);
    VertexColor = aColor;
    PickID      = aPickID;
}