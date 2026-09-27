// standard.vert
// Ana 3D element shader'ı (Frame, Area, Link, Node).
// MRT: hem renk (location 0) hem pick ID (location 1) yazar.

#version 460 core

// ---- Vertex input ----
layout(location = 0) in vec3 aPos;       // pozisyon (yerel veya aCenter'a göre offset)
layout(location = 1) in vec3 aNormal;    // yüzey normali
layout(location = 2) in vec3 aColor;     // vertex rengi
layout(location = 3) in uint aPickID;    // pick ID (her element için tekil)
layout(location = 4) in vec3 aCenter;    // merkez pozisyon (Node/Link için)

// ---- Fragment'e aktarılan ----
out vec3 FragPos;        // dünya uzayında pozisyon (ışık hesabı için)
flat out vec3 Normal;         // dünya uzayında normal
out vec3 VertexColor;    // vertex rengi
flat out uint vID;       // pick ID (interpolate edilmesin)

// ---- Uniform'lar ----
uniform mat4 model;
uniform mat3 normalMatrix;
uniform mat4 view;
uniform mat4 projection;
uniform mat4 mvp;

// Node/Link için ekran uzayında sabit boyut
uniform bool  isConstantSize = false;
uniform float pointScale     = 0.002;


void main() {
    vec4 worldPos;

    if (isConstantSize) {
        // --- Sabit ekran boyutu (Node, Link) ---
        // Kamera uzayındaki mesafeye göre ölçek
        vec4 viewCenter = view * vec4(aCenter, 1.0);
        float dist      = abs(viewCenter.z);
        float factor    = dist * pointScale;

        worldPos    = vec4(aCenter + (aPos * factor), 1.0);
        gl_Position = projection * view * worldPos;

    } else {
        // --- Normal 3D dönüşüm (Frame, Area) ---
        gl_Position = mvp * vec4(aPos, 1.0);
        worldPos    = model * vec4(aPos, 1.0);
    }

    FragPos     = vec3(worldPos);
    Normal      = normalize(normalMatrix * aNormal);
    VertexColor = aColor;
    vID         = aPickID;
}