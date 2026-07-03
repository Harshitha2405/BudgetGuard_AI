import aws_cdk as core
import aws_cdk.assertions as assertions

from budget_controller.budget_controller_stack import BudgetControllerStack

# example tests. To run these tests, uncomment this file along with the example
# resource in budget_controller/budget_controller_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = BudgetControllerStack(app, "budget-controller")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
