
from typing import Iterable, Tuple, List, Dict
from textwrap import dedent
from indra_cogex.client import Neo4jClient
from indra_cogex.representation import norm_id
from indra_cogex.client.enrichment.utils import minimum_evidence_helper
from indra.statements import Statement
from protmapper import uniprot_client
from indra.databases.hgnc_client import get_uniprot_id, get_hgnc_id

def get_neighbor_network(
        *,
        nodes: Iterable[Tuple[str, str]],
        client: Neo4jClient,
        upstream,
        downstream,
        minimum_evidence_count
) -> List[Statement]:
    
    nodes_str = ", ".join(["'%s'" % norm_id(*node) for node in nodes])

    if upstream and downstream:
        q = "p=(n2:BioEntity)-[r1:indra_rel]->(n1:BioEntity)-[r2:indra_rel]->(n3:BioEntity)"
    elif upstream and not downstream:
        q = "p=(n2:BioEntity)-[r1:indra_rel]->(n1:BioEntity)"
    elif not upstream and downstream:
        q = "p=(n1:BioEntity)-[r1:indra_rel]->(n2:BioEntity)"
    else:
        raise Exception("Either upstream or downstream must be True")

    query = f"""\
        MATCH {q}
        WHERE
            n1.id IN [{nodes_str}]
            AND n2.type = "human_gene_protein"
            AND r1.stmt_type IN ['IncreaseAmount', 'DecreaseAmount']
            AND n1.id <> n2.id
            {minimum_evidence_helper(minimum_evidence_count, "r1")}
        RETURN p
    """

    return client.query_relations(query)

def get_two_step_root(
    *,
    root_nodes: Iterable[Tuple[str, str]],
    downstream_nodes: Iterable[Tuple[str, str]],
    client: Neo4jClient
) -> List[Statement]:
    """Return the INDRA Statement subnetwork induced by paths of length
    two between nodes A and B in a query with intermediate nodes X such
    that paths look like A-X-B.

    Parameters
    ----------
    nodes :
        The nodes to query (A and B are one of these nodes in
        the following examples).
    client :
        The Neo4j client.

    Returns
    -------
    :
        The INDRA statement subnetwork induced by the query
    """
    
    root_nodes_str = ", ".join(["'%s'" % norm_id(*node) for node in root_nodes])
    downstream_nodes_str = ", ".join(["'%s'" % norm_id(*node) for node in downstream_nodes])

    query = dedent(
        f"""\
        MATCH p=(n1:BioEntity)-[r1:indra_rel]->(n3:BioEntity)-[r2:indra_rel]->(n2:BioEntity)
        WHERE
            n1.id IN [{root_nodes_str}]
            AND n2.id IN [{downstream_nodes_str}]
            AND n1.id <> n2.id
            AND n3.type = "human_gene_protein"
            AND r1.stmt_type IN ['IncreaseAmount', 'DecreaseAmount']
            AND r2.stmt_type IN ['IncreaseAmount', 'DecreaseAmount']
        RETURN p
        """
    )

    return client.query_relations(query)

def get_one_step_root_up(
    *,
    root_nodes: Iterable[Tuple[str, str]],
    client: Neo4jClient
    ) -> List[Statement]:
    """Return the INDRA Statement subnetwork induced by paths of length
    two between nodes A and B in a query with intermediate nodes X such
    that paths look like A-X-B.

    Parameters
    ----------
    nodes :
        The nodes to query (A and B are one of these nodes in
        the following examples).
    client :
        The Neo4j client.
    first_forward:
        If true, query A->X otherwise query A<-X
    second_forward:
        If true, query X->B otherwise query X<-B

    Returns
    -------
    :
        The INDRA statement subnetwork induced by the query
    """
    
    root_nodes_str = ", ".join(["'%s'" % norm_id(*node) for node in root_nodes])

    query = dedent(
        f"""\
        MATCH p=(n2:BioEntity)-[r1:indra_rel]->(n1:BioEntity)
        WHERE
            n1.id IN [{root_nodes_str}]
            AND n1.id <> n2.id
            AND n2.type = "human_gene_protein"
            AND r1.stmt_type IN ['IncreaseAmount', 'DecreaseAmount']
        RETURN p
        """
    )

    return client.query_relations(query)

def get_id(ids, id_type):
    if id_type == "uniprot":
        uniprot_ids = set(ids)

        hgnc_ids = set()
        failed = set()
        for uniprot_id in uniprot_ids:
            hgnc_id = uniprot_client.get_hgnc_id(uniprot_id)
            if hgnc_id:
                hgnc_ids.add(hgnc_id)
            else:
                failed.add(uniprot_id)

    elif id_type == "gene":
        hgnc_ids = set()
        failed = set()
        for gene_id in ids:
            hgnc_id = get_hgnc_id(gene_id)
            get_uniprot_id(gene_id)
            if hgnc_id:
                hgnc_ids.add(hgnc_id)
            else:
                failed.add(gene_id)
    
    hgnc_curies = [("hgnc", gene_id) for gene_id in hgnc_ids if gene_id is not None]

    return hgnc_curies

def query_between_relationships(nodes: Iterable[Tuple[str, str]], 
                                client: Neo4jClient,
                                relation: Iterable[str]) -> List[Dict]:
        
    nodes_str = ", ".join(["'%s'" % norm_id(*node) for node in nodes])
    query = dedent(
        f"""\
        MATCH p=(n1:BioEntity)-[r:indra_rel]->(n2:BioEntity)
        WHERE 
            n1.id IN [{nodes_str}]
            AND n2.id IN [{nodes_str}]
            AND n1.id <> n2.id
            AND r.stmt_type IN {relation}
        RETURN p
    """
    )
    return client.query_relations(query)

def query_confounder_relationships(nodes: Iterable[Tuple[str, str]], 
                                client: Neo4jClient,
                                minimum_evidence_count) -> List[Dict]:
        
    nodes_str = ", ".join(["'%s'" % norm_id(*node) for node in nodes])
    query = dedent(
        f"""\
        MATCH p=(n1:BioEntity)<-[r1:indra_rel]-(n3:BioEntity)-[r2:indra_rel]->(n2:BioEntity)
        WHERE
            n1.id IN [{nodes_str}]
            AND n2.id IN [{nodes_str}]
            AND n1.id <> n2.id
            AND NOT n3 IN [{nodes_str}]
            AND r1.stmt_type IN ['IncreaseAmount', 'DecreaseAmount']
            AND r2.stmt_type IN ['IncreaseAmount', 'DecreaseAmount']
            {minimum_evidence_helper(minimum_evidence_count, "r1")}
            {minimum_evidence_helper(minimum_evidence_count, "r2")}
        RETURN p
    """
    )
    return client.query_relations(query)

def query_mediator_relationships(nodes: Iterable[Tuple[str, str]], 
                                client: Neo4jClient,
                                relation: Iterable[str]) -> List[Dict]:
        
    nodes_str = ", ".join(["'%s'" % norm_id(*node) for node in nodes])
    query = dedent(
        f"""\
        MATCH p=(n1:BioEntity)-[r1:indra_rel]->(n3:BioEntity)-[r2:indra_rel]->(n2:BioEntity)
        WHERE
            n1.id IN [{nodes_str}]
            AND n2.id IN [{nodes_str}]
            AND n1.id <> n2.id
            AND NOT n3 IN [{nodes_str}]
            AND r1.stmt_type IN {relation}
            AND r2.stmt_type IN {relation}
        RETURN p
    """
    )
    return client.query_relations(query)