import aws_cdk as cdk

from budget_controller.budget_controller_stack import BudgetControllerStack

app = cdk.App()

BudgetControllerStack(app, "BudgetControllerStack")

app.synth()
