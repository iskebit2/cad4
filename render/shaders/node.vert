#version 460 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aColor;
layout(location = 3) in uint aPickId;

out vec3 VertexColor;
flat out uint VertexPickId;
flat out float PlaneOpacity;
uniform mat4 mvp;
uniform float pointSize;
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
    gl_PointSize = pointSize;
    VertexColor = aColor;
    VertexPickId = aPickId;
    PlaneOpacity = plane_opacity(aPickId);
}