// standard.vert
// Ana 3D element shader'ı (Frame, Area, Link, Node).
// MRT: renk (location 0) + pick ID (location 1).
//
// İki mod:
//   - isConstantSize=false → normal 3D dönüşüm (Frame, Area, Polygon)
//   - isConstantSize=true  → ekran uzayında sabit boyut (Node, Link)
//
// Vertex layout (9 float, Node/Link):
//   aPos (local) + aNormal + aCenter (global)

#version 460 core

// ---- Vertex input ----
layout(location = 0) in vec3  aPos;
layout(location = 1) in vec3  aNormal;
layout(location = 2) in vec3  aColor;
layout(location = 3) in uint  aPickID;
layout(location = 4) in vec3  aCenter;

// ---- Fragment'e aktarılan ----
out vec3      FragPos;
flat out vec3 Normal;
out vec3      VertexColor;
flat out uint vID;

// ---- Uniform'lar ----
uniform mat4 model;
uniform mat3 normalMatrix;
uniform mat4 view;
uniform mat4 projection;
uniform mat4 mvp;

// Node / Link için ekran uzayında sabit boyut
uniform bool  isConstantSize = false;
uniform float pointScale     = 0.002;

void main() {
    vec3 worldPos;

    if (isConstantSize) {
        // Ekran boyutu sabit — kamera uzayındaki mesafeye göre ölçek
        vec4 viewCenter = view * vec4(aCenter, 1.0);
        float factor    = abs(viewCenter.z) * pointScale;

        worldPos    = aCenter + aPos * factor;
        gl_Position = projection * view * vec4(worldPos, 1.0);
    } else {
        // Normal 3D dönüşüm
        worldPos    = (model * vec4(aPos, 1.0)).xyz;
        gl_Position = mvp * vec4(aPos, 1.0);
    }

    FragPos     = worldPos;
    Normal      = normalize(normalMatrix * aNormal);
    VertexColor = aColor;
    vID         = aPickID;
}