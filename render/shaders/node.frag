#version 460 core
in vec3 VertexColor;
out vec4 FragColor;

uniform bool useVertexColor;
uniform vec3 nodeColor;

void main() {
    vec3 color = useVertexColor ? VertexColor : nodeColor;
    
    // Nokta şekli için (isteğe bağlı yuvarlak)
    vec2 coord = gl_PointCoord - vec2(0.5);
    if (length(coord) > 0.5)
        discard;
    
    FragColor = vec4(color, 1.0);
}