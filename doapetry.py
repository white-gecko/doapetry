import sys
from contextlib import nullcontext
from pathlib import Path

import typer
from loguru import logger
from pyproject_parser import PyProject
from rdflib import DOAP, FOAF, RDF, RDFS, Graph, Literal, URIRef
from rdflib.namespace import Namespace

# Semantically-Interlinked Online Communities
# https://www.w3.org/submissions/sioc-spec/
SIOC = Namespace("http://rdfs.org/sioc/ns#")

# Semantically-Interlinked Online Developer Communities
SIODC = Namespace("https://siodc.example.org/#")

# Also this is a workaround
LICENSE_NAMESPACE = Namespace("https://spdx.org/licenses/")

README_TMP_CONTENT = "__tmp__"

app = typer.Typer()


@app.command()
def cli(
    project_path: str = ".", output: str = "-", base_url: str = "https://example.org/"
):
    """Return a Graph with a DOAP or None, if nothing could be found or it is unsupported."""

    # os.getcwd()

    if graph := doapetry(Path(project_path), base_url):
        with (
            open(output, mode="w")
            if output != "-"
            else nullcontext(sys.stdout) as output_stream
        ):
            print(graph.serialize(format="turtle"), file=output_stream)
            # graph.serialize(output_stream, format="turtle")


def doapetry(project_path: Path, base_url: str) -> Graph | None:
    """Return a Graph with a DOAP or None, if nothing could be found or it is unsupported."""

    pyproject_toml = project_path / "pyproject.toml"

    project = None
    attempts = 2
    for attempt in range(0, attempts):
        # This is a hack, since pyproject_parser only parses the pyproject.toml, if the README exists (?)
        try:
            logger.info(f"Load project from {pyproject_toml} …")
            project = PyProject.load(pyproject_toml)
            break
        except FileNotFoundError as e:
            logger.info(f"File {e.filename} was not found …")
            if e.filename == "README.md":
                logger.info(f"Create {e.filename} with temporary content.")
                with open(e.filename, "w") as readme_file:
                    readme_file.write(README_TMP_CONTENT)
    else:
        logger.error("Could not load the project.")

    g = pyproject_doap(project, base_url)

    # clean up
    readme = project_path / project.project.get("readme").file
    with open(readme, "r") as readme_file:
        if readme_file.read() == README_TMP_CONTENT:
            logger.info(f"Remove temporarily created {readme.file}.")
            readme.file.unlink()

    return g


def pyproject_doap(project: PyProject, base_url: str = "https://example.org/") -> Graph:
    """Construct a description based on the pyproject.toml."""
    project_dict = project.project
    g = Graph()
    project_resource = g.resource(base_url + project_dict.get("name"))

    project_resource.add(RDF.type, DOAP.Project)
    project_resource.add(DOAP.name, Literal(project_dict.get("name")))
    if description := project_dict.get("description"):
        project_resource.add(DOAP.shortdesc, Literal(description))
        project_resource.add(DOAP.description, Literal(description))
    for author in project_dict.get("authors") or []:
        email_iri = URIRef("mailto:" + author.get("email"))
        author_resource = g.resource(email_iri)
        # The typing is not yet cool, since doap:developer will make it a foaf:Person anyhow
        author_resource.add(RDF.type, FOAF.Agent)
        author_resource.add(FOAF.name, Literal(author.get("name")))
        author_resource.add(FOAF.mbox, email_iri)
        project_resource.add(DOAP.developer, author_resource)
    for maintainer in project_dict.get("maintainers") or []:
        email_iri = URIRef("mailto:" + maintainer.get("email"))
        maintainer_resource = g.resource(email_iri)
        # The typing is not yet cool, since doap:developer will make it a foaf:Person anyhow
        maintainer_resource.add(RDF.type, FOAF.Agent)
        maintainer_resource.add(FOAF.name, Literal(maintainer.get("name")))
        maintainer_resource.add(FOAF.mbox, email_iri)
        project_resource.add(DOAP.maintainer, maintainer_resource)
    if urls := project_dict.get("urls"):
        if homepage := urls.get("homepage"):
            project_resource.add(DOAP.homepage, URIRef(homepage))
        if repository := urls.get("repository"):
            repository_resource = g.resource(repository)
            project_resource.add(DOAP.repository, repository_resource)
            repository_resource.add(RDF.type, DOAP.Repository)
            repository_resource.add(DOAP.location, project_resource)
        if documentation := urls.get("documentation"):
            project_resource.add(DOAP.documentation, URIRef(documentation))
        if issue_tracker := urls.get("Bug Tracker"):
            project_resource.add(SIODC.issue_tracker, URIRef(issue_tracker))

    if project_license := project_dict.get("license"):
        if license_text := project_license.text:
            license_resource = g.resource(LICENSE_NAMESPACE[license_text])
            project_resource.add(DOAP.license, license_resource)
            license_resource.add(RDFS.label, Literal(license_text))

    return g


if __name__ == "__main__":
    app()
