#version 460 core

// ============================================================
// Inputs
// ============================================================

in vec3 VertexColor;

// Pick ID interpolasyon yapılmadan taşınır.
flat in uint ObjectID;


// ============================================================
// MRT outputs
// ============================================================

// Attachment 0 → normal renk
layout(location = 0) out vec4 FragColor;

// Attachment 1 → picking ID
layout(location = 1) out uint FragID;


// ============================================================
// Uniforms
// ============================================================

uniform bool useVertexColor;
uniform vec3 objectColor;
uniform float alpha;


// ============================================================
// Main
// ============================================================

void main()
{
    vec3 color = useVertexColor
        ? VertexColor
        : objectColor;

    // Normal görüntü
    FragColor = vec4(color, alpha);
    

    // Picking buffer
    FragID = ObjectID;
}