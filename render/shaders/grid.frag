// grid.frag
#version 460 core

in vec3 VertexColor;
out vec4 FragColor;

uniform float alpha;

void main() {
    FragColor = vec4(VertexColor, alpha);
}