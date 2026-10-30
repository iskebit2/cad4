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
flat out float PlaneOpacity;

// ---- Uniform ----
uniform mat4 mvp;
uniform bool  usePlaneFade   = false;
uniform float planeFadeAlpha = 0.22;

layout(std430, binding = 2) readonly buffer PlaneAssociationData {
    uint associatedCount;
    uint associatedIDs[];
};

float plane_opacity(uint elementID) {
    if (!usePlaneFade) {
        return 1.0;
    }

    uint low = 0u;
    uint high = associatedCount;
    while (low < high) {
        uint middle = low + (high - low) / 2u;
        uint candidate = associatedIDs[middle];
        if (candidate == elementID) {
            return 1.0;
        }
        if (candidate < elementID) {
            low = middle + 1u;
        } else {
            high = middle;
        }
    }
    return planeFadeAlpha;
}

void main() {
    gl_Position = mvp * vec4(aPos, 1.0);
    VertexColor = aColor;
    PickID      = aPickID;
    PlaneOpacity = plane_opacity(aPickID);
}