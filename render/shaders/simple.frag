// simple.frag
#version 460 core

in vec3 VertexColor;
out vec4 FragColor;

uniform bool useVertexColor;
uniform vec3 objectColor;
uniform float alpha;

void main() {
    vec3 color = useVertexColor ? VertexColor : objectColor;
    FragColor = vec4(color, alpha);
}