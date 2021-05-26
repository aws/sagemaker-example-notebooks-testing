import boto3

query = "CREATE EXTERNAL TABLE IF NOT EXISTS default.testing ( `date` date, `filename` string, `processing-job-name` string, `kernel` string, `output-notebook` string, `runtime` float, `status` string, `error` string ) ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe' WITH SERDEPROPERTIES ( 'serialization.format' = ',', 'field.delim' = ',' ) LOCATION 's3://sagemaker-us-west-2-521695447989/full_repo_scan/' TBLPROPERTIES ('has_encrypted_data'='false','skip.header.line.count'='1');"
DATABASE = "default"
output = "s3://aws-athena-query-results-521695447989-us-west-2/"


def lambda_handler(event, context):
    athena = boto3.client("athena")

    # Execution
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": DATABASE},
        ResultConfiguration={
            "OutputLocation": output,
        },
    )
    return response
