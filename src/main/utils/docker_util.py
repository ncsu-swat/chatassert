import docker

def delete_image(image_name, image_tag):
    client = docker.from_env()

    if client.images.list(name=f"{image_name}:{image_tag}"):
        client.images.remove(f"{image_name}:{image_tag}", force=True)
        print(f"Image {image_name}:{image_tag} removed successfully.")
    else:
        print(f"Image {image_name}:{image_tag} does not exist, skip removing.")



def build_image(image_name, image_tag, working_repo_dir):

    client = docker.from_env()

    # Build the image with the specified tag
    image = client.images.build(path=working_repo_dir, tag=f"{image_name}:{image_tag}")

    print(f"Image {image_name}:{image_tag} built successfully")

